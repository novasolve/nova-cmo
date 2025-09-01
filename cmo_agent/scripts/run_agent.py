#!/usr/bin/env python3
"""
CMO Agent Runner - Execute outbound campaigns
"""
import asyncio
import time
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

import yaml
from dotenv import load_dotenv
from tqdm.contrib.logging import logging_redirect_tqdm

# Ensure project root on sys.path for absolute imports
project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import modules with absolute package paths
from cmo_agent.agents.cmo_agent import CMOAgent
from cmo_agent.core.state import DEFAULT_CONFIG

# Load environment variables
load_dotenv()

from cmo_agent.core.monitoring import JsonExtraFormatter, configure_metrics_from_config
from cmo_agent.core.state import DEFAULT_CONFIG as _DEF

def _setup_logging_from_config(cfg: dict):
    log_cfg = cfg.get("logging", {}) if isinstance(cfg.get("logging"), dict) else {}
    log_level = getattr(logging, str(log_cfg.get("level", "INFO")).upper(), logging.INFO)
    logs_dir = Path(cfg.get("directories", _DEF.get("directories", {})).get("logs", "./logs"))
    logs_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(log_level)

    # Clear existing handlers to avoid duplicates
    for h in root.handlers[:]:
        root.removeHandler(h)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(log_level)
    ch.setFormatter(logging.Formatter(log_cfg.get("console_format", "%(asctime)s %(levelname)-4s %(message)s")))
    root.addHandler(ch)

    # File handler (JSONL)
    if log_cfg.get("json_file", True):
        fh_path = logs_dir / log_cfg.get("agent_log_file", "cmo_agent.jsonl")
        fh = logging.FileHandler(str(fh_path), encoding="utf-8")
        fh.setLevel(log_level)
        fh.setFormatter(JsonExtraFormatter())
        root.addHandler(fh)

    # Quiet noisy dependencies
    for noisy in ("httpx", "openai", "urllib3", "asyncio"):
        try:
            logging.getLogger(noisy).setLevel(logging.WARNING)
        except Exception:
            pass

    # Simple de-dup filter to reduce repeated log spam
    class _DedupFilter(logging.Filter):
        def __init__(self, window_s: float = 4.0, max_repeats: int = 3):
            super().__init__()
            self.window = window_s
            self.max_repeats = max_repeats
            self._last = {}
            self._count = {}
        def filter(self, record: logging.LogRecord) -> bool:
            key = (record.levelno, record.getMessage())
            now = time.monotonic()
            last = self._last.get(key, 0.0)
            if now - last > self.window:
                self._last[key] = now
                self._count[key] = 0
                return True
            self._count[key] = self._count.get(key, 0) + 1
            return self._count[key] in (1, self.max_repeats)

    dedup = _DedupFilter()
    for h in root.handlers:
        try:
            h.addFilter(dedup)
        except Exception:
            pass

_setup_logging_from_config(_DEF)
logger = logging.getLogger(__name__)


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from file and environment"""
    config = DEFAULT_CONFIG.copy()

    # Load from config file if provided
    if config_path and Path(config_path).exists():
        with open(config_path, 'r') as f:
            file_config = yaml.safe_load(f)
            config.update(file_config)

    # Override with environment variables
    env_mapping = {
        'GITHUB_TOKEN': 'GITHUB_TOKEN',
        'INSTANTLY_API_KEY': 'INSTANTLY_API_KEY',
        'ATTIO_API_KEY': 'ATTIO_API_KEY',
        'ATTIO_WORKSPACE_ID': 'ATTIO_WORKSPACE_ID',
        'LINEAR_API_KEY': 'LINEAR_API_KEY',
        'OPENAI_API_KEY': 'OPENAI_API_KEY',
    }

    for config_key, env_var in env_mapping.items():
        if os.getenv(env_var):
            config[config_key] = os.getenv(env_var)

    return config


async def run_campaign(goal: str, config_path: Optional[str] = None, dry_run: bool = False, no_emoji: bool = False, interactive: bool = False):
    """Run a CMO Agent campaign"""
    try:
        logger.info(f"Starting CMO Agent campaign: {goal}")
        # Friendly banner
        rocket = "🚀 " if not no_emoji else ""
        print(f"\n{rocket}Starting campaign…")
        t0 = time.perf_counter()

        # Load configuration
        config = load_config(config_path)
        logger.info(f"Loaded configuration from {config_path or 'defaults'}")
        # Reconfigure logging and monitoring according to loaded config
        _setup_logging_from_config(config)
        configure_metrics_from_config(config)

        # Validate environment early to fail fast with clear errors
        from pathlib import Path
        import sys
        
        # Add tools directory to path so we can import the env checker
        tools_dir = Path(__file__).parent.parent.parent / "tools"
        if tools_dir.exists():
            sys.path.insert(0, str(tools_dir))
            
        try:
            from check_env import check_environment
            env_result = check_environment(dry_run=dry_run)
            if env_result != 0:
                logger.error("Environment validation failed. Fix the issues above and try again.")
                return {"success": False, "error": "Environment validation failed"}
        except ImportError:
            # Fallback to basic validation if env checker isn't available
            logger.warning("Environment checker not found, using basic validation")
            github_token = str(config.get("GITHUB_TOKEN") or "").strip()
            if not dry_run:
                if not github_token:
                    logger.error("GITHUB_TOKEN is not set. Set it in your environment or .env, or pass --dry-run to skip external API calls.")
                    return {"success": False, "error": "Missing GITHUB_TOKEN"}
                # Warn on suspicious token formats (best-effort; tokens may change format)
                if not (github_token.startswith("ghp_") or github_token.startswith("github_pat_")):
                    logger.warning("GITHUB_TOKEN format doesn't match common patterns (ghp_*, github_pat_*). Continuing, but GitHub may return 401/403.")

        # Initialize agent
        agent = CMOAgent(config)
        logger.info("CMO Agent initialized successfully")
        print(("🔧 Initializing agent…" if not no_emoji else "Initializing agent…"))

        # Run the job
        if dry_run:
            # Ensure dry_run flag is visible to the agent/tools via config
            cfg_features = config.get('features') if isinstance(config.get('features'), dict) else {}
            cfg_features = {**cfg_features, 'dry_run': True}
            config['features'] = cfg_features
            agent.config = config
        print(("🔍 Discovering repositories…" if not no_emoji else "Discovering repositories…"))
        # Make tqdm play nicely with logging
        with logging_redirect_tqdm():
            result = await agent.run_job(goal)
        logger.info(f"Campaign completed: {result['success']}")

        # Helper functions for result processing
        from collections.abc import Mapping

        def as_map(x):
            if x is None:
                return {}
            if isinstance(x, Mapping):
                return x
            # Pydantic-style or custom objects
            for attr in ("to_dict", "dict", "model_dump"):
                if hasattr(x, attr):
                    try:
                        return getattr(x, attr)()
                    except Exception:
                        pass
            # Dict-like (has items/keys)
            try:
                return dict(x)
            except Exception:
                pass
            # Fallback: empty
            return {}

        def _generate_campaign_summary(final_state: dict, no_emoji: bool = False) -> str:
            """Generate a detailed campaign summary with distinct emails and counts"""
            
            # Icons
            icons = {
                'summary': '📋 ' if not no_emoji else '',
                'repos': '📦 ' if not no_emoji else '',
                'people': '👥 ' if not no_emoji else '',
                'emails': '📧 ' if not no_emoji else '',
                'leads': '🎯 ' if not no_emoji else '',
                'companies': '🏢 ' if not no_emoji else '',
                'locations': '🌍 ' if not no_emoji else '',
                'languages': '💻 ' if not no_emoji else '',
                'quality': '⭐ ' if not no_emoji else '',
                'success': '✅ ' if not no_emoji else '',
                'warning': '⚠️ ' if not no_emoji else '',
                'action': '🚀 ' if not no_emoji else '',
            }
            
            # Extract data - check if data is nested under 'agent' key (from checkpoint structure)
            agent_state = final_state.get('agent', final_state) if isinstance(final_state, dict) else final_state
            repos = agent_state.get('repos', [])
            candidates = agent_state.get('candidates', [])
            leads = agent_state.get('leads', [])
            icp = agent_state.get('icp', {})
            
            # Collect all emails found with detailed analysis
            all_emails = set()
            email_sources = {'profile': 0, 'commit': 0, 'public': 0, 'bio': 0, 'noreply': 0}
            email_quality_scores = []
            contactable_emails = []
            
            for lead in leads:
                email = lead.get('email')
                if email and '@' in email:
                    email_lower = email.lower()
                    
                    # Skip noreply emails but count them
                    if 'noreply' in email_lower or 'no-reply' in email_lower:
                        email_sources['noreply'] += 1
                        continue
                    
                    all_emails.add(email_lower)
                    contactable_emails.append({
                        'email': email,
                        'name': lead.get('name', lead.get('login', 'Unknown')),
                        'company': lead.get('company', ''),
                        'location': lead.get('location', ''),
                        'followers': lead.get('followers', 0),
                        'bio': lead.get('bio', '')
                    })
                    
                    # Track email source and quality
                    quality_score = 0
                    if lead.get('email_profile'):
                        email_sources['profile'] += 1
                        quality_score += 3  # Profile emails are high quality
                    elif 'gmail.com' in email_lower and lead.get('bio') and email_lower.split('@')[0] in lead.get('bio', ''):
                        email_sources['bio'] += 1
                        quality_score += 2  # Bio emails are medium quality
                    elif lead.get('email_public_commit') or lead.get('emails'):
                        email_sources['commit'] += 1
                        quality_score += 1  # Commit emails are lower quality
                    else:
                        email_sources['public'] += 1
                        quality_score += 2  # Public profile emails are medium quality
                    
                    # Bonus points for verification indicators
                    if lead.get('followers', 0) > 100:
                        quality_score += 1
                    if lead.get('company'):
                        quality_score += 1
                    
                    email_quality_scores.append(quality_score)
            
            # Collect companies
            companies = set()
            for lead in leads:
                company = lead.get('company')
                if company and company.strip():
                    companies.add(company.strip())
            
            # Collect locations
            locations = set()
            for lead in leads:
                location = lead.get('location')
                if location and location.strip():
                    locations.add(location.strip())
            
            # Collect languages from repos
            repo_languages = set()
            total_stars = 0
            for repo in repos:
                lang = repo.get('primary_language') or repo.get('language')
                if lang:
                    repo_languages.add(lang)
                stars = repo.get('stars', 0)
                if isinstance(stars, (int, float)):
                    total_stars += int(stars)
            
            # Build summary
            lines = []
            lines.append(f"\n{'='*60}")
            lines.append(f"{icons['summary']}CAMPAIGN SUMMARY")
            lines.append(f"{'='*60}")
            
            # WHO WE'RE TARGETING - Clear explanation at the top
            lines.append(f"\n🎯 WHO WE'RE TARGETING:")
            if icp and icp.get('goal'):
                # Parse the goal to create a human-readable explanation
                goal = icp['goal']
                lines.append(f"   Campaign Focus: {goal}")
                
                # Add context about what we're looking for
                if 'developer' in goal.lower():
                    lines.append(f"   👨‍💻 Seeking: Software developers and engineers")
                if 'python' in goal.lower():
                    lines.append(f"   🐍 Tech Stack: Python ecosystem contributors")
                if 'maintainer' in goal.lower():
                    lines.append(f"   🔧 Role Focus: Open source maintainers and core contributors")
                if 'active' in goal.lower() or 'activity' in goal.lower():
                    activity_days = icp.get('activity_days', 90)
                    lines.append(f"   ⚡ Activity: Recently active (last {activity_days} days)")
                
                # Show what we want to achieve
                lines.append(f"   📧 Goal: Find contactable leads for outbound campaigns")
                lines.append(f"   🎯 Outcome: Build targeted prospect list with verified emails")
            else:
                lines.append(f"   Campaign Focus: General prospect discovery")
            
            # ICP Criteria (detailed technical specs)
            if icp:
                lines.append(f"\n🔍 TECHNICAL CRITERIA:")
                if icp.get('languages'):
                    lines.append(f"   Languages: {', '.join(icp['languages'])}")
                if icp.get('keywords'):
                    lines.append(f"   Keywords: {', '.join(icp['keywords'])}")
                if icp.get('topics'):
                    lines.append(f"   Topics: {', '.join(icp['topics'][:5])}")  # Show first 5 topics
                if icp.get('stars_range'):
                    lines.append(f"   Repository Stars: {icp['stars_range']}")
                
                # Show target progress
                if icp.get('target_emails'):
                    target_emails = icp['target_emails']
                    progress_pct = min(100, (len(all_emails) / target_emails) * 100) if target_emails > 0 else 0
                    status = "✅" if progress_pct >= 100 else "🔄" if progress_pct >= 50 else "📈"
                    lines.append(f"   {status} Target Emails: {len(all_emails)}/{target_emails} ({progress_pct:.1f}%)")
                if icp.get('target_leads'):
                    target_leads = icp['target_leads']
                    progress_pct = min(100, (len(leads) / target_leads) * 100) if target_leads > 0 else 0
                    status = "✅" if progress_pct >= 100 else "🔄" if progress_pct >= 50 else "📈"
                    lines.append(f"   {status} Target Leads: {len(leads)}/{target_leads} ({progress_pct:.1f}%)")
            
            # Repository Summary
            lines.append(f"\n{icons['repos']}REPOSITORIES ANALYZED:")
            lines.append(f"   Total: {len(repos)}")
            if repo_languages:
                lines.append(f"   Languages: {', '.join(sorted(repo_languages))}")
            if total_stars > 0:
                lines.append(f"   Total Stars: {total_stars:,}")
            
            # People Summary
            lines.append(f"\n{icons['people']}PEOPLE DISCOVERED:")
            lines.append(f"   Candidates: {len(candidates)}")
            lines.append(f"   Leads (with email): {len([l for l in leads if l.get('email')])}")
            
            # Email Summary (enhanced with quality analysis)
            lines.append(f"\n{icons['emails']}EMAIL DISCOVERY & QUALITY ANALYSIS:")
            lines.append(f"   {icons['success']}Contactable Emails: {len(all_emails)}")
            lines.append(f"   {icons['warning']}Noreply/Blocked: {email_sources['noreply']}")
            
            # Quality breakdown
            if email_quality_scores:
                avg_quality = sum(email_quality_scores) / len(email_quality_scores)
                high_quality = sum(1 for score in email_quality_scores if score >= 4)
                medium_quality = sum(1 for score in email_quality_scores if 2 <= score < 4)
                low_quality = sum(1 for score in email_quality_scores if score < 2)
                
                lines.append(f"\n   {icons['quality']}EMAIL QUALITY BREAKDOWN:")
                lines.append(f"   {icons['success']}High Quality (4+ score): {high_quality}")
                lines.append(f"   🔶 Medium Quality (2-3 score): {medium_quality}")
                lines.append(f"   🔸 Low Quality (<2 score): {low_quality}")
                lines.append(f"   📊 Average Quality Score: {avg_quality:.1f}/6")
            
            # Source breakdown
            lines.append(f"\n   📍 EMAIL SOURCES:")
            if email_sources['profile'] > 0:
                lines.append(f"   • Profile Emails: {email_sources['profile']} {icons['success']}")
            if email_sources['bio'] > 0:
                lines.append(f"   • Bio Extracted: {email_sources['bio']} 🔶")
            if email_sources['public'] > 0:
                lines.append(f"   • Public Profile: {email_sources['public']} 🔶")
            if email_sources['commit'] > 0:
                lines.append(f"   • Commit History: {email_sources['commit']} 🔸")
            
            # Actionable contact list
            if len(contactable_emails) > 0:
                lines.append(f"\n   {icons['action']}TOP PROSPECTS FOR OUTREACH:")
                # Sort by quality (followers + company presence)
                sorted_contacts = sorted(contactable_emails, 
                                       key=lambda x: (x['followers'], bool(x['company']), bool(x['name'])), 
                                       reverse=True)
                
                for i, contact in enumerate(sorted_contacts[:10], 1):  # Show top 10
                    name = contact['name'] if contact['name'] != 'Unknown' else contact['email'].split('@')[0]
                    company_info = f" @ {contact['company']}" if contact['company'] else ""
                    location_info = f" ({contact['location']})" if contact['location'] else ""
                    followers_info = f" • {contact['followers']} followers" if contact['followers'] > 0 else ""
                    
                    lines.append(f"   {i:2d}. {name}{company_info}{location_info}{followers_info}")
                    lines.append(f"       📧 {contact['email']}")
                    
                if len(sorted_contacts) > 10:
                    lines.append(f"   ... and {len(sorted_contacts) - 10} more prospects")
                
                # Quick stats for outreach planning
                with_company = sum(1 for c in contactable_emails if c['company'])
                with_location = sum(1 for c in contactable_emails if c['location'])
                high_followers = sum(1 for c in contactable_emails if c['followers'] > 100)
                
                lines.append(f"\n   📈 OUTREACH INSIGHTS:")
                lines.append(f"   • {with_company}/{len(contactable_emails)} have company info ({with_company/len(contactable_emails)*100:.0f}%)")
                lines.append(f"   • {with_location}/{len(contactable_emails)} have location ({with_location/len(contactable_emails)*100:.0f}%)")
                lines.append(f"   • {high_followers}/{len(contactable_emails)} are influencers (100+ followers)")
            
            elif len(all_emails) == 0 and leads:
                lines.append(f"\n   {icons['warning']}No contactable emails found - all were noreply addresses")
                lines.append(f"   💡 Consider: LinkedIn outreach, GitHub issue engagement, or Twitter DMs")
            
            # Company Summary
            if companies:
                lines.append(f"\n{icons['companies']}COMPANIES REPRESENTED:")
                lines.append(f"   Distinct Companies: {len(companies)}")
                top_companies = sorted(companies)[:10]
                for company in top_companies:
                    lines.append(f"   • {company}")
                if len(companies) > 10:
                    lines.append(f"   ... and {len(companies) - 10} more")
            
            # Location Summary
            if locations:
                lines.append(f"\n{icons['locations']}GEOGRAPHIC DISTRIBUTION:")
                lines.append(f"   Distinct Locations: {len(locations)}")
                top_locations = sorted(locations)[:10]
                for location in top_locations:
                    lines.append(f"   • {location}")
                if len(locations) > 10:
                    lines.append(f"   ... and {len(locations) - 10} more")
            
            # Campaign Performance Summary
            lines.append(f"\n{icons['quality']}CAMPAIGN PERFORMANCE:")
            total_processed = len(candidates)
            leads_with_email = [l for l in leads if l.get('email')]
            conversion_rate = (len(leads_with_email) / total_processed * 100) if total_processed > 0 else 0
            email_success_rate = (len(all_emails) / len(leads_with_email) * 100) if len(leads_with_email) > 0 else 0
            
            lines.append(f"   📊 Lead Conversion (email-present): {len(leads_with_email)}/{total_processed} ({conversion_rate:.1f}%)")
            lines.append(f"   📧 Email Discovery: {len(all_emails)}/{len(leads_with_email)} ({email_success_rate:.1f}%)")
            
            if len(repos) > 0:
                avg_stars = sum(repo.get('stars', 0) for repo in repos) / len(repos)
                lines.append(f"   ⭐ Avg Repository Stars: {avg_stars:,.0f}")
            
            # Distinct Email List for easy copy-paste
            if len(all_emails) > 0:
                lines.append(f"\n📧 DISTINCT EMAIL ADDRESSES ({len(all_emails)} total):")
                sorted_emails = sorted(all_emails)
                for i, email in enumerate(sorted_emails, 1):
                    lines.append(f"   {i:2d}. {email}")
                
                # Add copy-paste friendly format
                lines.append(f"\n📋 COPY-PASTE FORMAT:")
                lines.append(f"   {', '.join(sorted_emails)}")
            
            # Next Steps & Recommendations
            lines.append(f"\n{icons['action']}RECOMMENDED NEXT STEPS:")
            
            if len(all_emails) > 0:
                lines.append(f"   1. {icons['success']}Export contact list to CSV for outreach tools")
                lines.append(f"   2. 📝 Craft personalized messages mentioning their repos/contributions")
                lines.append(f"   3. 🎯 Prioritize high-quality prospects (4+ score) for initial outreach")
                if high_quality > 0:
                    lines.append(f"   4. 🚀 Start with {high_quality} high-quality prospects for best ROI")
                lines.append(f"   5. 📊 Track response rates to optimize future campaigns")
            else:
                lines.append(f"   1. {icons['warning']}Expand search criteria - try different keywords/topics")
                lines.append(f"   2. 🔍 Consider alternative contact methods (LinkedIn, Twitter)")
                lines.append(f"   3. 📈 Target repositories with more recent activity")
                lines.append(f"   4. 🎯 Focus on specific niches within Python ecosystem")
            
            # Data Export Info
            if len(all_emails) > 0:
                lines.append(f"\n💾 DATA EXPORT:")
                lines.append(f"   • Contact data saved to campaign checkpoint")
                lines.append(f"   • Use export_csv tool to create outreach-ready spreadsheet")
                lines.append(f"   • Includes: names, emails, companies, locations, GitHub profiles")
            
            lines.append(f"{'='*60}")
            
            return '\n'.join(lines)

        # Print summary
        if result.get('success'):
            raw_final_state = as_map(result.get('final_state'))
            # Extract the actual agent state data (nested under 'agent' key)
            final_state = raw_final_state.get('agent', raw_final_state) if 'agent' in raw_final_state else raw_final_state
            report = as_map(result.get('report'))
            summary = as_map(report.get('summary'))
            counters = as_map(final_state.get('counters'))

            def to_int(value, default=0) -> int:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return int(default)

            leads_list = final_state.get('leads')
            leads_with_email_list = [l for l in (leads_list or []) if isinstance(l, dict) and l.get('email')]
            leads_count = len(leads_with_email_list)
            to_send_list = final_state.get('to_send')
            to_send_count = len(to_send_list) if isinstance(to_send_list, list) else 0

            repos_count = len(final_state.get('repos', []))
            candidates_count = len(final_state.get('candidates', []))
            stats = {
                "steps": max(to_int(summary.get("steps_completed"), 0), to_int(counters.get("steps"), 0)),
                "api_calls": max(to_int(summary.get("api_calls_made"), 0), to_int(counters.get("api_calls"), 0)),
                "repos": repos_count,
                "candidates": candidates_count,
                "leads": max(to_int(summary.get("leads_processed"), 0), leads_count),
                "emails_prepared": max(to_int(summary.get("emails_prepared"), 0), to_send_count),
                "duration_s": round(time.perf_counter() - t0, 2),
            }

            party = "🎉 " if not no_emoji else ""
            chart = "📊 " if not no_emoji else ""
            email_icon = "📧 " if not no_emoji else ""
            building = "🏢 " if not no_emoji else ""
            
            # Debug: Check what data we're getting
            print(f"\n🔍 DEBUG: final_state keys: {list(final_state.keys())}")
            if 'repos' in final_state:
                print(f"🔍 DEBUG: repos count: {len(final_state.get('repos', []))}")
            if 'icp' in final_state:
                print(f"🔍 DEBUG: icp data: {final_state.get('icp', {})}")
            
            # Generate detailed campaign summary
            campaign_summary = _generate_campaign_summary(final_state, no_emoji)
            print(campaign_summary)
            
            print(f"\n{party}Campaign completed successfully!")
            print(f"{chart}Stats: {stats}")
            print(f"{email_icon}Emails prepared: {stats['emails_prepared']}")

            reports = as_map(final_state.get("reports"))
            attio = reports.get("attio", {}) if isinstance(reports.get("attio", {}), dict) else {}
            synced_people = attio.get("synced_people", []) if isinstance(attio.get("synced_people", []), list) else []
            print(f"{building}CRM sync: {len(synced_people)}")

            # Print absolute path to the latest checkpoint for easy access
            try:
                checkpoints = final_state.get("checkpoints", [])
                if isinstance(checkpoints, list) and checkpoints:
                    last_path = checkpoints[-1].get("path")
                    if last_path:
                        abs_path = str(Path(last_path).resolve())
                        puzzle = "🧩 " if not no_emoji else ""
                        print(f"{puzzle}Checkpoint: {abs_path}")
            except Exception:
                pass

            # Optional interactive continuation
            if interactive:
                answer = input(("Run another campaign? (y/N): "))
                if answer.strip().lower() in ["y", "yes"]:
                    next_goal = input("Enter goal for next campaign: ")
                    return await run_campaign(next_goal, config_path=config_path, dry_run=dry_run, no_emoji=no_emoji, interactive=interactive)
        else:
            # Show summary even for failed campaigns to show what was accomplished
            raw_final_state = as_map(result.get('final_state'))
            # Extract the actual agent state data (nested under 'agent' key)
            final_state = raw_final_state.get('agent', raw_final_state) if 'agent' in raw_final_state else raw_final_state
            
            if final_state:
                campaign_summary = _generate_campaign_summary(final_state, no_emoji)
                print(campaign_summary)
                # Also show checkpoint path when available on failure
                try:
                    checkpoints = final_state.get("checkpoints", [])
                    if isinstance(checkpoints, list) and checkpoints:
                        last_path = checkpoints[-1].get("path")
                        if last_path:
                            abs_path = str(Path(last_path).resolve())
                            puzzle = "🧩 " if not no_emoji else ""
                            print(f"{puzzle}Checkpoint: {abs_path}")
                except Exception:
                    pass
            
            cross = "❌ " if not no_emoji else ""
            print(f"\n{cross}Campaign failed: {result.get('error', 'Unknown error')}")

        return result

    except Exception as e:
        logger.error(f"Campaign execution failed: {e}")
        print(f"\n💥 Critical error: {e}")
        return {"success": False, "error": str(e)}


def main():
    """Main CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="CMO Agent - Outbound Campaign Automation")
    parser.add_argument(
        "goal",
        help="Campaign goal (e.g., 'Find 2k Py maintainers active 90d, queue Instantly seq=123')"
    )
    parser.add_argument(
        "--config",
        "-c",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (no actual sending)"
    )
    parser.add_argument(
        "--no-emoji",
        action="store_true",
        help="Disable emoji in CLI output"
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Prompt to run another campaign after completion"
    )

    args = parser.parse_args()

    # Modify goal for dry-run
    if args.dry_run:
        args.goal += " (DRY RUN - no actual sending)"

    # Ensure log directory exists
    Path("./logs").mkdir(exist_ok=True)

    # Run the campaign
    result = asyncio.run(run_campaign(args.goal, args.config, dry_run=args.dry_run, no_emoji=args.no_emoji, interactive=args.interactive))

    # Exit with appropriate code
    sys.exit(0 if result.get('success', False) else 1)


if __name__ == "__main__":
    main()
