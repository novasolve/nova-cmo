#!/usr/bin/env python3
"""
Lead Intelligence Engine
Main orchestration system that coordinates data collection, analysis, and intelligence generation
"""

import os
import sys
import json
import yaml
import time
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict
from pathlib import Path
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import timezone utilities
from .timezone_utils import utc_now, to_utc_iso8601

# Add parent directory to path to import existing scraper
sys.path.append(str(Path(__file__).parent.parent.parent))

from github_prospect_scraper import GitHubScraper, Prospect
from .data_validator import DataValidator
from .error_handler import ErrorHandler
from .attio_integrator import AttioIntegrator
from .repo_enricher import RepoEnricher
from .export_engine import ExportEngine
# Import analysis modules locally to avoid relative import issues
# from ..analysis.scoring_model import LeadScorer
# from ..analysis.personalization_engine import PersonalizationEngine

# Import beautiful logging system
from .beautiful_logger import beautiful_logger, log_header, log_separator, create_progress_bar


class DataManager:
    """Manages data organization and storage"""

    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.raw_dir = self.base_dir / "raw"
        self.processed_dir = self.base_dir / "processed"
        self.backup_dir = self.base_dir / "backups"
        self.metadata_dir = self.base_dir / "metadata"

        # Create directories
        for dir_path in [self.raw_dir, self.processed_dir, self.backup_dir, self.metadata_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def save_raw_data(self, data: Any, filename: str) -> str:
        """Save raw data with timestamp"""
        timestamp = utc_now().strftime('%Y%m%d_%H%M%S')
        file_path = self.raw_dir / f"{filename}_{timestamp}.json"

        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

        return str(file_path)

    def save_processed_data(self, data: Any, filename: str) -> str:
        """Save processed data"""
        file_path = self.processed_dir / f"{filename}.json"

        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

        return str(file_path)

    def create_backup(self, data: Any, filename: str) -> str:
        """Create backup of data"""
        timestamp = utc_now().strftime('%Y%m%d_%H%M%S')
        file_path = self.backup_dir / f"{filename}_backup_{timestamp}.json"

        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

        return str(file_path)

    def save_metadata(self, metadata: Dict[str, Any], filename: str) -> str:
        """Save metadata"""
        file_path = self.metadata_dir / f"{filename}_metadata.json"

        with open(file_path, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)

        return str(file_path)

    def get_latest_file(self, pattern: str, directory: str = "processed") -> Optional[str]:
        """Get the latest file matching pattern"""
        dir_path = getattr(self, f"{directory}_dir")
        files = list(dir_path.glob(pattern))

        if not files:
            return None

        return str(max(files, key=lambda x: x.stat().st_mtime))


@dataclass
class IntelligenceConfig:
    """Configuration for the lead intelligence system"""
    github_token: str
    base_config_path: str = "config.yaml"
    output_dir: str = "lead_intelligence/data"
    analysis_dir: str = "lead_intelligence/analysis"
    reporting_dir: str = "lead_intelligence/reporting"
    enrichment_enabled: bool = True
    scoring_enabled: bool = True
    max_workers: int = 4
    cache_ttl_hours: int = 24
    validation_enabled: bool = True
    error_handling_enabled: bool = True
    attio_integration_enabled: bool = True
    attio_api_token: str = ""
    backup_enabled: bool = True
    logging_level: str = "INFO"
    max_repos: int = 40
    max_leads: int = 200

    # Filtering options
    location_filter: str = "us"
    language_filter: str = "english"
    english_only: bool = True
    us_only: bool = True


@dataclass
class LeadIntelligence:
    """Enhanced lead with intelligence metrics"""
    prospect: Prospect
    intelligence_score: float
    quality_signals: List[str]
    enrichment_data: Dict[str, Any]
    risk_factors: List[str]
    opportunity_signals: List[str]
    engagement_potential: str
    analysis_timestamp: datetime

    def to_dict(self):
        data = asdict(self.prospect)
        data.update({
            'intelligence_score': self.intelligence_score,
            'quality_signals': ','.join(self.quality_signals),
            'enrichment_data': json.dumps(self.enrichment_data),
            'risk_factors': ','.join(self.risk_factors),
            'opportunity_signals': ','.join(self.opportunity_signals),
            'engagement_potential': self.engagement_potential,
            'analysis_timestamp': self.analysis_timestamp.isoformat()
        })
        return data


class IntelligenceEngine:
    """Main intelligence orchestration engine"""

    def __init__(self, config: IntelligenceConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.setup_logging()
        self.setup_directories()

        # Load base configuration
        self.base_config = self.load_base_config()

        # Override limits from simple config if provided
        if hasattr(config, 'max_repos') and config.max_repos != 40:
            self.base_config.setdefault('limits', {})['max_repos'] = config.max_repos
        if hasattr(config, 'max_leads') and config.max_leads != 200:
            self.base_config.setdefault('limits', {})['max_people'] = config.max_leads

        # Initialize core components
        self.scraper = GitHubScraper(
            token=config.github_token or os.environ.get('GITHUB_TOKEN', ''),
            config=self.base_config,
            output_path=None,
            output_dir=config.output_dir
        )

        # Initialize advanced components
        self.validator = DataValidator() if config.validation_enabled else None
        self.error_handler = ErrorHandler() if config.error_handling_enabled else None

        # Initialize Attio integrator with proper configuration
        attio_config = {
            'api_token': config.attio_api_token,
            'workspace_id': os.environ.get('ATTIO_WORKSPACE_ID', ''),
            'base_url': 'https://api.attio.com/v2/',
            'batch_size': 50,
            'rate_limit_delay': 1.0,
            'max_retries': 3,
            'timeout': 30,
            'auto_create_lists': True,
            'validate_before_import': True,
            'backup_before_import': True
        }

        self.attio_integrator = AttioIntegrator(attio_config) if config.attio_integration_enabled and config.attio_api_token else None

        if self.attio_integrator:
            self.logger.info("🔗 Attio integrator initialized")
            if not self.attio_integrator.validate_connection():
                self.logger.warning("⚠️  Attio connection validation failed - integration will be skipped")
                self.attio_integrator = None
            else:
                self.logger.info("✅ Attio connection validated successfully")
        else:
            self.logger.info("ℹ️  Attio integration disabled or no API token provided")

        # Initialize new intelligence components
        self.repo_enricher = RepoEnricher(config.github_token or os.environ.get('GITHUB_TOKEN', ''))

        # Import analysis modules locally to avoid relative import issues
        import sys
        sys.path.append(str(Path(__file__).parent.parent))
        from analysis.scoring_model import LeadScorer
        from analysis.personalization_engine import PersonalizationEngine

        self.lead_scorer = LeadScorer()
        self.personalization_engine = PersonalizationEngine()
        self.export_engine = ExportEngine(config.output_dir)

        # Intelligence components
        self.analyzers = []
        self.enrichers = []
        self.scorers = []

        # Data organization
        self.data_manager = DataManager(config.output_dir)

    def setup_logging(self):
        """Setup logging configuration"""
        logging.getLogger().setLevel(getattr(logging, self.config.logging_level))

    def setup_directories(self):
        """Create necessary directories"""
        dirs = [
            self.config.output_dir,
            self.config.analysis_dir,
            self.config.reporting_dir,
            f"{self.config.output_dir}/raw",
            f"{self.config.output_dir}/processed",
            f"{self.config.output_dir}/intelligence",
            f"{self.config.analysis_dir}/reports",
            f"{self.config.analysis_dir}/metrics",
            f"{self.config.reporting_dir}/dashboards",
            f"{self.config.reporting_dir}/exports"
        ]

        for dir_path in dirs:
            Path(dir_path).mkdir(parents=True, exist_ok=True)

    def load_base_config(self) -> dict:
        """Load the base GitHub scraper configuration"""
        config_path = Path(self.config.base_config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Base config not found: {config_path}")

        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    async def run_intelligence_cycle(self) -> Dict[str, Any]:
        """Run the comprehensive lead intelligence pipeline following the specified workflow"""
        log_header("🚀 Lead Intelligence Pipeline")
        beautiful_logger.phase_start("Pipeline", "Starting comprehensive lead intelligence")

        pipeline_metadata = {
            'start_time': to_utc_iso8601(utc_now()),
            'pipeline_version': '2.0',
            'phases': {},
            'errors': [],
            'warnings': []
        }

        try:
            # Phase 1: Ingest leads (from GitHub scraper)
            beautiful_logger.phase_start("1/7 Lead Ingestion", "Pulling leads from GitHub scraper")
            raw_leads = await self.ingest_leads()
            beautiful_logger.data_stats("Leads ingested", len(raw_leads))
            pipeline_metadata['phases']['ingestion'] = {
                'leads_ingested': len(raw_leads),
                'timestamp': to_utc_iso8601(utc_now())
            }

            if not raw_leads:
                beautiful_logger.logger.warning("⚠️  No leads to process - pipeline complete")
                return self._create_empty_pipeline_result(pipeline_metadata)

            # Phase 2: Fetch repo snapshots (enrich with CI health, activity)
            beautiful_logger.phase_start("2/7 Repository Enrichment", "Fetching CI health and activity data")
            enriched_leads = await self.enrich_repositories(raw_leads)
            repos_count = len(set(l.get('repo') for l in enriched_leads if l.get('repo')))
            beautiful_logger.enrichment_complete(f"{repos_count} repositories", ["CI", "activity", "languages", "tests"])
            pipeline_metadata['phases']['enrichment'] = {
                'leads_enriched': len(enriched_leads),
                'repos_snapshots_created': repos_count,
                'timestamp': to_utc_iso8601(utc_now())
            }

            # Phase 3: Extract features (CI flake score, patchability score, etc.)
            beautiful_logger.phase_start("3/7 Feature Extraction", "Calculating priority scores and risk assessment")
            scored_leads = await self.extract_features_and_score(enriched_leads)
            high_priority = len([l for l in scored_leads if l.get('priority_score', 0) > 0.7])
            low_risk = len([l for l in scored_leads if l.get('deliverability_risk', 1) < 0.3])
            beautiful_logger.scoring_complete(len(scored_leads), high_priority, low_risk)
            pipeline_metadata['phases']['scoring'] = {
                'leads_scored': len(scored_leads),
                'high_priority_count': high_priority,
                'low_risk_count': low_risk,
                'timestamp': to_utc_iso8601(utc_now())
            }

            # Phase 4: Cohort & personalize (generate Repo Briefs)
            beautiful_logger.phase_start("4/7 Personalization", "Generating AI-powered repo briefs and cohort analysis")
            personalized_leads = await self.generate_personalization(scored_leads)
            cohorts = list(set(l.get('cohort', {}).get('stars_bucket', 'unknown') for l in personalized_leads))
            beautiful_logger.personalization_complete(len(personalized_leads), cohorts)
            pipeline_metadata['phases']['personalization'] = {
                'leads_personalized': len(personalized_leads),
                'repo_briefs_generated': len(personalized_leads),
                'cohorts_identified': len(cohorts),
                'timestamp': to_utc_iso8601(utc_now())
            }

            # Phase 5: Quality gates & select Monday wave
            beautiful_logger.phase_start("5/7 Quality Gates", "Applying deliverability filters and selecting Monday wave")
            monday_wave_leads = await self.apply_quality_gates(personalized_leads)
            qualified_rate = len(monday_wave_leads) / len(personalized_leads) if personalized_leads and len(personalized_leads) > 0 else 0.0
            beautiful_logger.phase_end("Quality Gates", {
                'qualified': len(monday_wave_leads),
                'total': len(personalized_leads),
                'rate': f"{qualified_rate:.1%}"
            })
            pipeline_metadata['phases']['quality_gates'] = {
                'total_candidates': len(personalized_leads),
                'monday_wave_selected': len(monday_wave_leads),
                'qualified_rate': qualified_rate,
                'timestamp': to_utc_iso8601(utc_now())
            }

            # Phase 6: Export Instantly CSV + repo briefs
            beautiful_logger.phase_start("6/7 Campaign Export", "Generating Instantly CSV and repo briefs")
            export_results = await self.export_campaign_materials(monday_wave_leads)
            if export_results.get('success'):
                beautiful_logger.export_complete("campaign", export_results.get('files', []), export_results.get('leads_exported', 0))
            pipeline_metadata['phases']['export'] = export_results

            # Phase 7: Push to Attio & Linear (optional)
            beautiful_logger.phase_start("7/7 CRM Integration", "Syncing with Attio and Linear")
            crm_results = await self.integrate_with_crm(monday_wave_leads)
            if crm_results.get('attio_push_attempted'):
                beautiful_logger.crm_sync("Attio", 0)  # Will be updated when implemented
            pipeline_metadata['phases']['crm_integration'] = crm_results

            # Success summary
            pipeline_metadata['end_time'] = to_utc_iso8601(utc_now())
            pipeline_metadata['success'] = True
            pipeline_metadata['summary'] = {
                'total_leads_processed': len(raw_leads),
                'monday_wave_size': len(monday_wave_leads),
                'conversion_rate': len(monday_wave_leads) / len(raw_leads) if raw_leads else 0,
                'export_files_created': len(export_results.get('files', []))
            }

            # Beautiful final summary
            beautiful_logger.phase_end("Lead Intelligence Pipeline", {
                'leads_processed': len(raw_leads),
                'monday_wave': len(monday_wave_leads),
                'conversion_rate': f"{pipeline_metadata['summary']['conversion_rate']:.1%}",
                'export_files': len(export_results.get('files', []))
            })

            # Display pipeline summary with beautiful formatting
            summary_stats = {
                'total_leads_processed': len(raw_leads),
                'monday_wave_qualified': len(monday_wave_leads),
                'conversion_rate': pipeline_metadata['summary']['conversion_rate'],
                'export_files_created': len(export_results.get('files', [])),
                'processing_time_seconds': (datetime.now() - datetime.fromisoformat(pipeline_metadata['start_time'])).total_seconds()
            }
            beautiful_logger.pipeline_summary(summary_stats)

        except Exception as e:
            pipeline_metadata['success'] = False
            pipeline_metadata['end_time'] = to_utc_iso8601(utc_now())
            pipeline_metadata['errors'].append({
                'error': str(e),
                'phase': 'unknown',
                'timestamp': to_utc_iso8601(utc_now())
            })

            beautiful_logger.error_banner("PIPELINE ERROR", str(e))

            if self.error_handler:
                self.error_handler.handle_error(e, {'phase': 'pipeline'}, 'pipeline_error')
            else:
                beautiful_logger.logger.error(f"Pipeline failed: {e}")

        # Save pipeline metadata
        self.data_manager.save_metadata(pipeline_metadata, 'intelligence_pipeline')

        return {
            'pipeline_metadata': pipeline_metadata,
            'monday_wave_leads': monday_wave_leads if 'monday_wave_leads' in locals() else [],
            'export_results': export_results if 'export_results' in locals() else {},
            'success': pipeline_metadata.get('success', False)
        }

    async def ingest_leads(self) -> List[Dict[str, Any]]:
        """Phase 1: Ingest leads from GitHub scraper"""
        try:
            prospects = await self.collect_data()
            # Convert to dict format expected by the pipeline
            leads = []
            for prospect in prospects:
                lead = prospect.to_dict()
                # Add any missing fields expected by the pipeline
                lead.setdefault('maintainer_name', lead.get('login', ''))
                lead.setdefault('repo_url', lead.get('github_repo_url', ''))
                lead.setdefault('description', lead.get('repo_description', ''))
                leads.append(lead)

            return leads

        except Exception as e:
            self.logger.error(f"Lead ingestion failed: {e}")
            return []

    async def enrich_repositories(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Phase 2: Fetch repo snapshots with CI health and activity data"""
        enriched_leads = []

        for lead in leads:
            try:
                repo_full_name = lead.get('repo_full_name') or lead.get('repo', '')
                if repo_full_name:
                    enrichment = self.repo_enricher.enrich_repo(repo_full_name)
                    lead['enrichment'] = enrichment
                else:
                    lead['enrichment'] = {}
                    self.logger.warning(f"No repo name found for lead: {lead.get('login', 'unknown')}")

                enriched_leads.append(lead)

            except Exception as e:
                self.logger.error(f"Failed to enrich repo {lead.get('repo', 'unknown')}: {e}")
                lead['enrichment'] = {'error': str(e)}
                enriched_leads.append(lead)

        return enriched_leads

    async def extract_features_and_score(self, enriched_leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Phase 3: Extract features and calculate priority + risk scores"""
        scored_leads = []

        for lead in enriched_leads:
            try:
                # Calculate scores
                score_result = self.lead_scorer.score_lead(lead, lead.get('enrichment', {}))

                # Add scores to lead data
                lead['priority_score'] = score_result.priority_score
                lead['deliverability_risk'] = score_result.deliverability_risk
                lead['component_scores'] = score_result.component_scores
                lead['risk_factors'] = score_result.risk_factors
                lead['priority_signals'] = score_result.priority_signals
                lead['cohort'] = score_result.cohort
                lead['scoring_recommendation'] = score_result.recommendation

                scored_leads.append(lead)

            except Exception as e:
                self.logger.error(f"Failed to score lead {lead.get('login', 'unknown')}: {e}")
                # Add default scores
                lead['priority_score'] = 0.5
                lead['deliverability_risk'] = 0.5
                lead['scoring_recommendation'] = 'manual_review'
                scored_leads.append(lead)

        return scored_leads

    async def generate_personalization(self, scored_leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Phase 4: Generate personalized repo briefs and cohort analysis"""
        personalized_leads = []

        for lead in scored_leads:
            try:
                # Generate repo brief
                repo_brief = self.personalization_engine.generate_repo_brief(
                    lead, lead.get('enrichment', {}), lead.get('cohort', {})
                )

                # Generate Instantly row
                instantly_row = self.personalization_engine.generate_instantly_row(repo_brief)

                # Add to lead data
                lead['repo_brief'] = {
                    'email': repo_brief.email,
                    'first_name': repo_brief.first_name,
                    'repo': repo_brief.repo,
                    'one_line_context': repo_brief.one_line_context,
                    'personalization_snippet': repo_brief.personalization_snippet,
                    'subject_options': repo_brief.subject_options,
                    'body_short': repo_brief.body_short,
                    'risk_flags': repo_brief.risk_flags,
                    'cohort': repo_brief.cohort
                }
                lead['instantly_row'] = {
                    'email': instantly_row.email,
                    'first_name': instantly_row.first_name,
                    'repo': instantly_row.repo,
                    'language': instantly_row.language,
                    'personalization_snippet': instantly_row.personalization_snippet,
                    'subject': instantly_row.subject,
                    'body': instantly_row.body,
                    'unsub': instantly_row.unsub
                }

                personalized_leads.append(lead)

            except Exception as e:
                self.logger.error(f"Failed to personalize lead {lead.get('login', 'unknown')}: {e}")
                # Add basic personalization
                lead['repo_brief'] = {'error': str(e)}
                lead['instantly_row'] = {'error': str(e)}
                personalized_leads.append(lead)

        return personalized_leads

    async def apply_quality_gates(self, personalized_leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Phase 5: Apply quality gates and select Monday wave candidates"""
        qualified_leads = []

        for lead in personalized_leads:
            try:
                # Apply quality gates
                priority_score = lead.get('priority_score', 0)
                risk_score = lead.get('deliverability_risk', 1)

                # Ensure numeric types for comparison
                try:
                    priority_score = float(priority_score) if priority_score is not None else 0.0
                    risk_score = float(risk_score) if risk_score is not None else 1.0
                except (ValueError, TypeError):
                    priority_score = 0.0
                    risk_score = 1.0

                # Quality gate: priority > 0.4 AND risk < 0.5
                if priority_score > 0.4 and risk_score < 0.5:
                    qualified_leads.append(lead)

                # Additional quality checks
                instantly_row = lead.get('instantly_row', {})
                if instantly_row.get('error'):
                    continue  # Skip leads with personalization errors

                # Email validation
                email = lead.get('email', '')
                if not email or '@' not in email:
                    continue

                # Remove role-based emails
                if any(role in email.lower() for role in ['admin@', 'info@', 'noreply@']):
                    continue

            except Exception as e:
                self.logger.error(f"Quality gate failed for lead {lead.get('login', 'unknown')}: {e}")
                continue

        # Sort by priority score (descending) and select top 2200 (2000 + 200 buffer)
        qualified_leads.sort(key=lambda x: x.get('priority_score', 0), reverse=True)
        monday_wave = qualified_leads[:2200]

        beautiful_logger.data_stats("Quality Gates Applied", len(monday_wave), {
            'qualified_total': len(qualified_leads),
            'conversion_rate': f"{len(monday_wave)/len(qualified_leads):.1%}" if qualified_leads and len(qualified_leads) > 0 else "0%"
        })

        return monday_wave

    async def export_campaign_materials(self, monday_wave_leads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Phase 6: Export Instantly CSV and repo briefs"""
        try:
            # Extract Instantly rows and repo briefs
            instantly_rows = []
            repo_briefs = []

            for lead in monday_wave_leads:
                instantly_row = lead.get('instantly_row')
                repo_brief = lead.get('repo_brief')

                if instantly_row and not instantly_row.get('error'):
                    # Convert dict to InstantlyRow object
                    # Import here to avoid relative import issues
                    import sys
                    sys.path.append(str(Path(__file__).parent.parent))
                    from analysis.personalization_engine import InstantlyRow
                    row = InstantlyRow(
                        email=instantly_row.get('email', ''),
                        first_name=instantly_row.get('first_name', ''),
                        repo=instantly_row.get('repo', ''),
                        language=instantly_row.get('language', ''),
                        personalization_snippet=instantly_row.get('personalization_snippet', ''),
                        subject=instantly_row.get('subject', ''),
                        body=instantly_row.get('body', ''),
                        unsub=instantly_row.get('unsub', '')
                    )
                    instantly_rows.append(row)

                if repo_brief and not repo_brief.get('error'):
                    repo_briefs.append(repo_brief)

            # Export using export engine
            campaign_results = self.export_engine.create_campaign_package(
                instantly_rows, repo_briefs, "monday_wave"
            )

            return {
                'success': True,
                'campaign_dir': campaign_results['campaign_dir'],
                'files': campaign_results['files'],
                'leads_exported': len(instantly_rows),
                'briefs_exported': len(repo_briefs)
            }

        except Exception as e:
            self.logger.error(f"Export failed: {e}")
            return {'success': False, 'error': str(e)}

    async def integrate_with_crm(self, monday_wave_leads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Phase 7: Push to Attio and prepare Linear tasks"""
        crm_results = {
            'attio_push_attempted': False,
            'attio_push_successful': False,
            'linear_tasks_prepared': len(monday_wave_leads)
        }

        # Attio integration (if configured)
        if self.attio_integrator and monday_wave_leads:
            try:
                self.logger.info(f"🔗 Pushing {len(monday_wave_leads)} leads to Attio...")

                # Prepare Attio data from monday wave leads
                attio_data = self.prepare_attio_data_from_leads(monday_wave_leads)

                # Import data into Attio
                import_results = self.attio_integrator.import_intelligence_data(attio_data)

                crm_results['attio_result'] = import_results
                crm_results['attio_push_attempted'] = True
                crm_results['attio_push_successful'] = import_results.get('overall', {}).get('success_rate', 0) > 0

                if crm_results['attio_push_successful']:
                    self.logger.info(f"✅ Successfully pushed {import_results.get('overall', {}).get('total_successful', 0)} records to Attio")
                else:
                    self.logger.warning(f"⚠️  Attio push completed with errors. Success rate: {import_results.get('overall', {}).get('success_rate', 0)*100:.1f}%")

            except Exception as e:
                self.logger.error(f"❌ Attio integration failed: {e}")
                crm_results['attio_error'] = str(e)
                crm_results['attio_push_attempted'] = True
                crm_results['attio_push_successful'] = False

                # Provide helpful error messages
                if "401" in str(e):
                    self.logger.error("💡 Attio authentication failed. Check your ATTIO_API_TOKEN")
                elif "403" in str(e):
                    self.logger.error("💡 Attio permission denied. Check your API key permissions")
                elif "404" in str(e):
                    self.logger.error("💡 Attio objects not found. Run 'make attio-objects' to create them")
                else:
                    self.logger.error("💡 Check your Attio configuration and network connection")

        # Linear task preparation (metadata for follow-up)
        crm_results['linear_tasks'] = []
        for lead in monday_wave_leads[:10]:  # Just prepare metadata for top 10
            task = {
                'title': f"{lead.get('maintainer_name', 'Unknown')} @ {lead.get('repo', 'unknown')} - Follow-up",
                'priority': 'high' if lead.get('priority_score', 0) > 0.8 else 'normal',
                'labels': ['OSS', 'Inbound', lead.get('cohort', {}).get('lang', 'unknown')],
                'lead_email': lead.get('email', ''),
                'repo': lead.get('repo', ''),
                'priority_score': lead.get('priority_score', 0)
            }
            crm_results['linear_tasks'].append(task)

        return crm_results

    def prepare_attio_data_from_leads(self, monday_wave_leads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Prepare Attio data format from Monday wave leads"""
        attio_data = {
            'people': [],
            'repos': [],
            'memberships': [],
            'signals': []
        }

        # Extract people data
        for lead in monday_wave_leads:
            # Get the best available email
            email = lead.get('email') or lead.get('email_profile') or lead.get('email_public_commit')
            if not email:
                continue  # Skip leads without email

            person_data = {
                'login': lead.get('maintainer_name', '').lower().replace(' ', ''),
                'name': lead.get('maintainer_name', ''),
                'company': lead.get('company'),
                'location': lead.get('location'),
                'bio': f"Maintains {lead.get('repo', '')}. Intelligence score: {lead.get('priority_score', 0):.2f}",
                'public_repos': 1,  # We'll update this if we have actual data
                'followers': lead.get('followers', 0),
                'html_url': f"https://github.com/{lead.get('maintainer_name', '')}",
                'github_user_url': f"https://github.com/{lead.get('maintainer_name', '')}",
                'api_url': f"https://api.github.com/users/{lead.get('maintainer_name', '')}",
                'created_at': lead.get('created_at'),
                'updated_at': lead.get('updated_at'),
                'email_profile': email,
                'lead_id': lead.get('lead_id'),
                'priority_score': lead.get('priority_score', 0),
                'deliverability_risk': lead.get('deliverability_risk', 0.5),
                'engagement_potential': lead.get('engagement_potential', 'medium')
            }
            attio_data['people'].append(person_data)

            # Extract repository data
            repo_name = lead.get('repo', '')
            if repo_name:
                repo_data = {
                    'repo_full_name': repo_name,
                    'repo_name': repo_name.split('/')[-1],
                    'owner_login': repo_name.split('/')[0],
                    'host': 'GitHub',
                    'description': lead.get('description', ''),
                    'primary_language': lead.get('language', ''),
                    'stars': lead.get('stars', 0),
                    'forks': lead.get('forks', 0),
                    'watchers': lead.get('watchers', 0),
                    'html_url': lead.get('repo_url', ''),
                    'api_url': f"https://api.github.com/repos/{repo_name}",
                    'topics': lead.get('topics', ''),
                    'has_ci': lead.get('has_ci', False),
                    'last_failed_ci': lead.get('last_failed_ci'),
                    'python_versions_in_matrix': lead.get('python_versions_in_matrix', '')
                }
                attio_data['repos'].append(repo_data)

                # Extract membership data (relationship between person and repo)
                membership_data = {
                    'membership_id': f"{lead.get('maintainer_name', '')}_{repo_name}",
                    'login': lead.get('maintainer_name', ''),
                    'repo_full_name': repo_name,
                    'role': 'maintainer',
                    'contributions_past_year': lead.get('contributions_last_year', 0),
                    'last_activity_at': lead.get('signal_at')
                }
                attio_data['memberships'].append(membership_data)

            # Extract signal data
            signal_data = {
                'signal_id': f"{lead.get('lead_id', '')}_{lead.get('signal_at', '')}",
                'signal_type': lead.get('signal_type', 'repo_owner'),
                'signal': lead.get('signal', ''),
                'signal_at': lead.get('signal_at', ''),
                'url': lead.get('github_repo_url', ''),
                'source': 'GitHub Intelligence',
                'repo_full_name': lead.get('repo', ''),
                'login': lead.get('maintainer_name', ''),
                'priority_score': lead.get('priority_score', 0),
                'cohort': lead.get('cohort', {})
            }
            attio_data['signals'].append(signal_data)

        self.logger.info(f"Prepared Attio data: {len(attio_data['people'])} people, {len(attio_data['repos'])} repos, {len(attio_data['memberships'])} memberships, {len(attio_data['signals'])} signals")
        return attio_data

    def _create_empty_pipeline_result(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Create empty result when no leads are processed"""
        metadata['end_time'] = to_utc_iso8601(utc_now())
        metadata['success'] = True
        metadata['summary'] = {
            'total_leads_processed': 0,
            'monday_wave_size': 0,
            'conversion_rate': 0,
            'export_files_created': 0
        }

        return {
            'pipeline_metadata': metadata,
            'monday_wave_leads': [],
            'export_results': {},
            'success': True
        }

    async def run_demo_cycle(self) -> Dict[str, Any]:
        """Run intelligence cycle with demo data for testing purposes"""
        log_header("🎭 Demo Intelligence Pipeline")
        beautiful_logger.phase_start("Demo Mode", "Running with sample data for testing")

        cycle_metadata = {
            'start_time': to_utc_iso8601(utc_now()),
            'config': asdict(self.config),
            'phases': {},
            'demo_mode': True,
            'errors': [],
            'warnings': []
        }

        try:
            # Generate demo prospects
            demo_prospects = self._generate_demo_prospects()
            cycle_metadata['phases']['demo_data_generation'] = {
                'prospects_generated': len(demo_prospects),
                'timestamp': to_utc_iso8601(utc_now())
            }

            # Phase 1: Data Collection (simulated)
            self.logger.info("📊 Phase 1: Demo Data Collection")
            # Save demo data
            raw_data = [p.to_dict() for p in demo_prospects]
            raw_file = self.data_manager.save_raw_data(raw_data, 'demo_prospects')
            cycle_metadata['phases']['collection'] = {
                'prospects_collected': len(demo_prospects),
                'timestamp': to_utc_iso8601(utc_now()),
                'demo_mode': True
            }

            # Phase 2: Data Validation
            if self.validator:
                self.logger.info("✅ Phase 2: Data Validation")
                validation_results = self.validator.validate_batch(raw_data)
                cycle_metadata['phases']['validation'] = validation_results

                # Generate validation report
                validation_report = self.validator.generate_quality_report(validation_results)
                self.data_manager.save_metadata({'validation_report': validation_report}, 'demo_validation')

            # Phase 3: Intelligence Analysis
            self.logger.info("🧠 Phase 3: Intelligence Analysis")
            intelligent_leads = await self.analyze_and_enrich(demo_prospects)
            cycle_metadata['phases']['analysis'] = {
                'leads_processed': len(intelligent_leads),
                'timestamp': to_utc_iso8601(utc_now()),
                'demo_mode': True
            }

            # Phase 4: Attio Integration (skipped in demo)
            self.logger.info("🔗 Phase 4: Attio Integration (Skipped in demo mode)")
            cycle_metadata['phases']['attio_integration'] = {
                'skipped': True,
                'reason': 'demo_mode'
            }

            # Phase 5: Generate Reports
            self.logger.info("📊 Phase 5: Report Generation")
            report_results = await self.generate_reports(intelligent_leads)
            cycle_metadata['phases']['reporting'] = report_results

            cycle_metadata['end_time'] = to_utc_iso8601(utc_now())
            cycle_metadata['success'] = True

            self.logger.info(f"✅ Demo intelligence cycle complete. Processed {len(intelligent_leads)} demo leads")

        except Exception as e:
            cycle_metadata['success'] = False
            cycle_metadata['end_time'] = to_utc_iso8601(utc_now())
            cycle_metadata['errors'].append({
                'error': str(e),
                'timestamp': to_utc_iso8601(utc_now())
            })

            if self.error_handler:
                self.error_handler.handle_error(e, {'phase': 'demo_cycle'}, 'general')
            else:
                self.logger.error(f"Demo cycle failed: {e}")

        # Save cycle metadata
        self.data_manager.save_metadata(cycle_metadata, 'demo_intelligence_cycle')

        return {
            'intelligent_leads': intelligent_leads if 'intelligent_leads' in locals() else [],
            'metadata': cycle_metadata,
            'success': cycle_metadata.get('success', False)
        }


            events_url='https://api.github.com/users/johndoe/events{/privacy}',
            received_events_url='https://api.github.com/users/johndoe/received_events',
            twitter_username=None,
            blog='https://johndoe.dev',
            linkedin_username=None,
            hireable=True,
            public_repos=35,
            public_gists=12,
            followers=250,
            following=120,
            total_private_repos=None,
            owned_private_repos=None,
            private_gists=None,
            disk_usage=None,
            collaborators=None,
            contributions_last_year=450,
            total_contributions=450,
            longest_streak=None,
            current_streak=None,
            created_at='2016-01-15T10:30:00Z',
            updated_at='2024-01-15T10:30:00Z',
            type='User',
            site_admin=False,
            gravatar_id='',
            suspended_at=None,
            plan_name='free',
            plan_space=976562499,
            plan_collaborators=0,
            plan_private_repos=10000,
            two_factor_authentication=True,
            has_organization_projects=True,
            has_repository_projects=True
        )
        demo_prospects.append(prospect1)

        # Demo prospect 2: Sarah Smith
        prospect2 = Prospect(
            lead_id=67890,
            login='sarahsmith',
            id=678901,
            node_id='MDQ6VXNlcjY3ODkwMQ==',
            name='Sarah Smith',
            company='DataSys LLC',
            email_public_commit=None,
            email_profile='sarah.smith@datasys.com',
            location='New York, NY',
            bio='Data Scientist specializing in NLP and recommendation systems',
            pronouns=None,
            repo_full_name='sarahsmith/nlp-tools',
            repo_description='Advanced NLP tools and utilities',
            signal='Developed advanced NLP toolkit',
            signal_type='repo_owner',
            signal_at='2024-02-20T14:45:00Z',
            topics='nlp,machine-learning,python',
            language='python',
            stars=800,
            forks=45,
            watchers=23,
            github_user_url='https://github.com/sarahsmith',
            github_repo_url='https://github.com/sarahsmith/nlp-tools',
            avatar_url='https://github.com/images/error/sarahsmith_happy.gif',
            html_url='https://github.com/sarahsmith',
            api_url='https://api.github.com/users/sarahsmith',
            followers_url='https://api.github.com/users/sarahsmith/followers',
            following_url='https://api.github.com/users/sarahsmith/following{/other_user}',
            gists_url='https://api.github.com/users/sarahsmith/gists{/gist_id}',
            starred_url='https://api.github.com/users/sarahsmith/starred{/owner}{/repo}',
            subscriptions_url='https://api.github.com/users/sarahsmith/subscriptions',
            organizations_url='https://api.github.com/users/sarahsmith/orgs',
            repos_url='https://api.github.com/users/sarahsmith/repos',
            events_url='https://api.github.com/users/sarahsmith/events{/privacy}',
            received_events_url='https://api.github.com/users/sarahsmith/received_events',
            twitter_username='sarahsmith_ds',
            blog='https://sarahsmith.com',
            linkedin_username=None,
            hireable=True,
            public_repos=28,
            public_gists=8,
            followers=180,
            following=95,
            total_private_repos=None,
            owned_private_repos=None,
            private_gists=None,
            disk_usage=None,
            collaborators=None,
            contributions_last_year=320,
            total_contributions=320,
            longest_streak=None,
            current_streak=None,
            created_at='2017-02-20T14:45:00Z',
            updated_at='2024-02-20T14:45:00Z',
            type='User',
            site_admin=False,
            gravatar_id='',
            suspended_at=None,
            plan_name='free',
            plan_space=976562499,
            plan_collaborators=0,
            plan_private_repos=10000,
            two_factor_authentication=True,
            has_organization_projects=True,
            has_repository_projects=True
        )
        demo_prospects.append(prospect2)

        # Demo prospect 3: Mike Johnson
        prospect3 = Prospect(
            lead_id=11111,
            login='mikejohnson',
            id=111112,
            node_id='MDQ6VXNlcjExMTExMg==',
            name='Mike Johnson',
            company=None,
            email_public_commit='mike.j@example.com',
            email_profile=None,
            location='Austin, TX',
            bio='Full-stack developer with expertise in React and Node.js',
            pronouns=None,
            repo_full_name='mikejohnson/web-framework',
            repo_description='Modern web development framework',
            signal='Built modern web framework',
            signal_type='repo_owner',
            signal_at='2024-03-10T09:15:00Z',
            topics='javascript,react,node.js,web-development',
            language='javascript',
            stars=450,
            forks=67,
            watchers=34,
            github_user_url='https://github.com/mikejohnson',
            github_repo_url='https://github.com/mikejohnson/web-framework',
            avatar_url='https://github.com/images/error/mikejohnson_happy.gif',
            html_url='https://github.com/mikejohnson',
            api_url='https://api.github.com/users/mikejohnson',
            followers_url='https://api.github.com/users/mikejohnson/followers',
            following_url='https://api.github.com/users/mikejohnson/following{/other_user}',
            gists_url='https://api.github.com/users/mikejohnson/gists{/gist_id}',
            starred_url='https://api.github.com/users/mikejohnson/starred{/owner}{/repo}',
            subscriptions_url='https://api.github.com/users/mikejohnson/subscriptions',
            organizations_url='https://api.github.com/users/mikejohnson/orgs',
            repos_url='https://api.github.com/users/mikejohnson/repos',
            events_url='https://api.github.com/users/mikejohnson/events{/privacy}',
            received_events_url='https://api.github.com/users/mikejohnson/received_events',
            twitter_username=None,
            blog=None,
            linkedin_username=None,
            hireable=False,
            public_repos=22,
            public_gists=15,
            followers=95,
            following=150,
            total_private_repos=None,
            owned_private_repos=None,
            private_gists=None,
            disk_usage=None,
            collaborators=None,
            contributions_last_year=280,
            total_contributions=280,
            longest_streak=None,
            current_streak=None,
            created_at='2018-03-10T09:15:00Z',
            updated_at='2024-03-10T09:15:00Z',
            type='User',
            site_admin=False,
            gravatar_id='',
            suspended_at=None,
            plan_name='free',
            plan_space=976562499,
            plan_collaborators=0,
            plan_private_repos=10000,
            two_factor_authentication=False,
            has_organization_projects=True,
            has_repository_projects=True
        )
        demo_prospects.append(prospect3)

        return demo_prospects

    async def integrate_with_attio(self, intelligent_leads: List[LeadIntelligence]) -> Dict[str, Any]:
        """Integrate processed data with Attio CRM"""
        try:
            # Prepare data for Attio import
            attio_data = self.prepare_attio_data(intelligent_leads)

            # Import data into Attio
            import_results = self.attio_integrator.import_intelligence_data(attio_data)

            # Save import results
            self.data_manager.save_metadata(import_results, 'attio_import')

            return import_results

        except Exception as e:
            self.logger.error(f"Attio integration failed: {e}")
            if self.error_handler:
                self.error_handler.handle_error(e, {'phase': 'attio_integration'}, 'attio_error')
            return {'error': str(e)}

    def prepare_attio_data(self, intelligent_leads: List[LeadIntelligence]) -> Dict[str, Any]:
        """Prepare intelligence data for Attio import"""
        attio_data = {
            'people': [],
            'repos': [],
            'memberships': [],
            'signals': []
        }

        # Extract people data
        for lead in intelligent_leads:
            person_data = {
                'login': lead.prospect.login,
                'id': lead.prospect.id,
                'node_id': lead.prospect.node_id,
                'lead_id': lead.prospect.lead_id,
                'name': lead.prospect.name,
                'company': lead.prospect.company,
                'email_profile': lead.prospect.email_profile,
                'email_public_commit': lead.prospect.email_public_commit,
                'location': lead.prospect.location,
                'bio': lead.prospect.bio,
                'pronouns': lead.prospect.pronouns,
                'public_repos': lead.prospect.public_repos,
                'public_gists': lead.prospect.public_gists,
                'followers': lead.prospect.followers,
                'following': lead.prospect.following,
                'html_url': lead.prospect.html_url,
                'avatar_url': lead.prospect.avatar_url,
                'github_user_url': lead.prospect.github_user_url,
                'api_url': lead.prospect.api_url,
                'created_at': lead.prospect.created_at,
                'updated_at': lead.prospect.updated_at
            }
            attio_data['people'].append(person_data)

        # Extract repository data from prospects
        repo_data = {}
        for lead in intelligent_leads:
            repo_key = lead.prospect.repo_full_name
            if repo_key not in repo_data:
                repo_data[repo_key] = {
                    'repo_full_name': lead.prospect.repo_full_name,
                    'repo_name': lead.prospect.repo_full_name.split('/')[-1],
                    'owner_login': lead.prospect.repo_full_name.split('/')[0],
                    'host': 'GitHub',
                    'description': lead.prospect.repo_description,
                    'primary_language': lead.prospect.language,
                    'stars': lead.prospect.stars,
                    'forks': lead.prospect.forks,
                    'watchers': lead.prospect.watchers,
                    'open_issues': None,  # Not available in current data
                    'is_fork': None,
                    'is_archived': None,
                    'html_url': lead.prospect.github_repo_url,
                    'api_url': None,
                    'created_at': None,
                    'updated_at': None,
                    'pushed_at': None
                }

        attio_data['repos'] = list(repo_data.values())

        return attio_data

    async def collect_data(self) -> List[Prospect]:
        """Collect raw prospect data using existing scraper with improved organization"""
        self.logger.info("📊 Phase 1: Data Collection")

        try:
            # Create backup of existing data if enabled
            if self.config.backup_enabled:
                existing_data = self.data_manager.get_latest_file("*.json", "processed")
                if existing_data:
                    with open(existing_data, 'r') as f:
                        backup_data = json.load(f)
                    self.data_manager.create_backup(backup_data, 'pre_collection_backup')

            # Run the existing scraper
            self.scraper.scrape()

            # Get the collected prospects
            prospects = self.scraper.all_prospects

            # Save raw data with proper organization
            raw_data = [p.to_dict() for p in prospects]
            raw_file = self.data_manager.save_raw_data(raw_data, 'raw_prospects')

            # Save collection metadata
            collection_metadata = {
                'collection_timestamp': to_utc_iso8601(utc_now()),
                'prospects_collected': len(prospects),
                'raw_data_file': raw_file,
                'scraper_config': asdict(self.config)
            }
            self.data_manager.save_metadata(collection_metadata, 'collection')

            self.logger.info(f"📥 Collected {len(prospects)} raw prospects - saved to {raw_file}")
            return prospects

        except Exception as e:
            self.logger.error(f"Data collection failed: {e}")
            if self.error_handler:
                self.error_handler.handle_error(e, {'phase': 'collection'}, 'collection_error')
            raise

    async def analyze_and_enrich(self, prospects: List[Prospect]) -> List[LeadIntelligence]:
        """Analyze and enrich prospects with intelligence"""
        self.logger.info("🧠 Phase 2: Intelligence Analysis & Enrichment")

        intelligent_leads = []

        # Process prospects in parallel
        with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
            futures = [executor.submit(self.process_single_lead, prospect) for prospect in prospects]

            for future in as_completed(futures):
                try:
                    lead = future.result()
                    if lead:
                        intelligent_leads.append(lead)
                except Exception as e:
                    self.logger.error(f"Error processing lead: {e}")

        # Sort by intelligence score
        intelligent_leads.sort(key=lambda x: x.intelligence_score, reverse=True)

        # Save processed data with proper organization
        processed_data = [lead.to_dict() for lead in intelligent_leads]
        processed_file = self.data_manager.save_processed_data(processed_data, 'intelligent_leads')

        # Save analysis metadata
        analysis_metadata = {
            'analysis_timestamp': to_utc_iso8601(utc_now()),
            'leads_analyzed': len(intelligent_leads),
            'processed_data_file': processed_file,
            'scoring_enabled': self.config.scoring_enabled,
            'enrichment_enabled': self.config.enrichment_enabled
        }
        self.data_manager.save_metadata(analysis_metadata, 'analysis')

        self.logger.info(f"🎯 Processed {len(intelligent_leads)} intelligent leads - saved to {processed_file}")
        return intelligent_leads

    def process_single_lead(self, prospect: Prospect) -> Optional[LeadIntelligence]:
        """Process a single prospect through intelligence pipeline"""
        try:
            # Apply filtering first
            if not self._passes_filters(prospect):
                return None
            # Basic analysis
            intelligence_score = self.calculate_intelligence_score(prospect)
            quality_signals = self.identify_quality_signals(prospect)
            risk_factors = self.identify_risk_factors(prospect)
            opportunity_signals = self.identify_opportunity_signals(prospect)
            engagement_potential = self.assess_engagement_potential(prospect)

            # Enrichment
            enrichment_data = {}
            if self.config.enrichment_enabled:
                enrichment_data = self.enrich_lead_data(prospect)

            return LeadIntelligence(
                prospect=prospect,
                intelligence_score=intelligence_score,
                quality_signals=quality_signals,
                enrichment_data=enrichment_data,
                risk_factors=risk_factors,
                opportunity_signals=opportunity_signals,
                engagement_potential=engagement_potential,
                analysis_timestamp=datetime.now()
            )

        except Exception as e:
            self.logger.error(f"Error processing prospect {prospect.login}: {e}")
            return None

    def _passes_filters(self, prospect: Prospect) -> bool:
        """Check if prospect passes location and language filters"""
        try:
            # Location filtering
            if self.config.us_only and isinstance(self.config.us_only, bool):
                location = getattr(prospect, 'location', '') or ''
                location_lower = location.lower()

                # Check for US indicators
                us_indicators = ['us', 'usa', 'united states', 'america', 'california', 'new york',
                               'texas', 'florida', 'washington', 'san francisco', 'los angeles',
                               'seattle', 'austin', 'miami', 'chicago', 'boston', 'denver']

                # Check if location contains US indicators
                has_us_indicator = any(indicator in location_lower for indicator in us_indicators)

                # If no clear US indicators and location is specified, exclude
                if location and not has_us_indicator:
                    return False

            # Language filtering
            if self.config.english_only and isinstance(self.config.english_only, bool):
                # Check bio for English indicators
                bio = getattr(prospect, 'bio', '') or ''
                bio_lower = bio.lower()

                # English language indicators
                english_indicators = ['python', 'developer', 'engineer', 'software', 'data',
                                    'machine learning', 'ai', 'web', 'backend', 'frontend',
                                    'full stack', 'devops', 'cloud', 'aws', 'docker', 'kubernetes']

                # Check if bio contains English technical terms
                has_english_content = any(indicator in bio_lower for indicator in english_indicators)

                # If bio exists but no English indicators, exclude
                if bio and not has_english_content:
                    return False

                # Check company name for English indicators
                company = getattr(prospect, 'company', '') or ''
                company_lower = company.lower()

                english_company_indicators = ['inc', 'llc', 'corp', 'ltd', 'co', 'labs', 'tech',
                                            'software', 'systems', 'solutions', 'group']

                has_english_company = any(indicator in company_lower for indicator in english_company_indicators)

                # If company exists but no English indicators, exclude
                if company and not has_english_company and not has_english_content:
                    return False

            return True

        except Exception as e:
            self.logger.warning(f"Error applying filters to {prospect.login}: {e}")
            return True  # Default to including if filtering fails

    def calculate_intelligence_score(self, prospect: Prospect) -> float:
        """Calculate overall intelligence score for a prospect"""
        score = 0.0

        # Email quality (highest weight)
        if prospect.has_email():
            score += 3.0
            # Bonus for profile email vs commit email
            if prospect.email_profile:
                score += 1.0

        # GitHub engagement
        if prospect.followers is not None and prospect.followers > 50:
            score += min(prospect.followers / 100, 2.0)

        # Repository context
        if prospect.stars is not None and prospect.stars > 100:
            score += min(prospect.stars / 500, 2.0)

        # Company information
        if prospect.company:
            score += 1.0

        # Location information
        if prospect.location:
            score += 0.5

        # Bio completeness
        if prospect.bio:
            score += 0.5

        # Recent activity
        if prospect.contributions_last_year and prospect.contributions_last_year > 10:
            score += min(prospect.contributions_last_year / 50, 1.5)

        return round(score, 2)

    def identify_quality_signals(self, prospect: Prospect) -> List[str]:
        """Identify positive quality signals"""
        signals = []

        if prospect.has_email():
            signals.append("has_email")
        if prospect.email_profile:
            signals.append("profile_email")
        if prospect.company:
            signals.append("has_company")
        if prospect.location:
            signals.append("has_location")
        if prospect.bio and len(prospect.bio) > 50:
            signals.append("detailed_bio")
        if prospect.followers is not None and prospect.followers > 100:
            signals.append("high_followers")
        if prospect.public_repos is not None and prospect.public_repos > 20:
            signals.append("active_contributor")
        if prospect.contributions_last_year is not None and prospect.contributions_last_year > 50:
            signals.append("highly_active")

        return signals

    def identify_risk_factors(self, prospect: Prospect) -> List[str]:
        """Identify potential risk factors"""
        risks = []

        if not prospect.has_email():
            risks.append("no_email")
        if not prospect.company:
            risks.append("no_company")
        if not prospect.location:
            risks.append("no_location")
        if prospect.followers is not None and prospect.followers < 5:
            risks.append("low_followers")
        if prospect.public_repos is not None and prospect.public_repos < 3:
            risks.append("low_activity")
        if prospect.contributions_last_year is not None and prospect.contributions_last_year < 5:
            risks.append("low_recent_activity")

        return risks

    def identify_opportunity_signals(self, prospect: Prospect) -> List[str]:
        """Identify opportunity signals"""
        opportunities = []

        # Recent activity signals
        if prospect.contributions_last_year and prospect.contributions_last_year > 20:
            opportunities.append("high_recent_activity")

        # Repository quality signals
        if prospect.stars is not None and prospect.stars > 500:
            opportunities.append("popular_repository")

        # Technical signals
        if prospect.language and prospect.language.lower() in ['python', 'javascript', 'typescript', 'go', 'rust']:
            opportunities.append("modern_tech_stack")

        # Professional signals
        if prospect.hireable:
            opportunities.append("open_to_opportunities")

        return opportunities

    def assess_engagement_potential(self, prospect: Prospect) -> str:
        """Assess overall engagement potential"""
        score = self.calculate_intelligence_score(prospect)

        if score >= 5.0:
            return "high"
        elif score >= 3.0:
            return "medium"
        elif score >= 1.0:
            return "low"
        else:
            return "minimal"

    def enrich_lead_data(self, prospect: Prospect) -> Dict[str, Any]:
        """Enrich lead with additional intelligence data"""
        enrichment = {}

        try:
            # LinkedIn URL extraction
            linkedin = prospect.get_linkedin()
            if linkedin:
                enrichment['linkedin_url'] = linkedin

            # Domain analysis
            if prospect.has_email():
                email = prospect.get_best_email()
                if email and '@' in email:
                    domain = email.split('@')[1]
                    enrichment['email_domain'] = domain
                    enrichment['is_corporate_email'] = not self._is_public_email_domain(domain)

            # Company domain inference
            if prospect.company:
                enrichment['company_normalized'] = prospect.company.strip().lstrip('@').lower()
            elif prospect.company is not None:
                enrichment['company_normalized'] = prospect.company.lstrip('@').lower()

            # Technology stack inference
            if prospect.language:
                enrichment['primary_technology'] = prospect.language.lower()

            # Activity patterns
            if prospect.contributions_last_year:
                enrichment['activity_level'] = "high" if prospect.contributions_last_year > 50 else "medium" if prospect.contributions_last_year > 10 else "low"

        except Exception as e:
            self.logger.error(f"Error enriching data for {prospect.login}: {e}")

        return enrichment

    def _is_public_email_domain(self, domain: str) -> bool:
        """Check if domain is a public email provider"""
        public_domains = {
            'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
            'aol.com', 'proton.me', 'protonmail.com', 'icloud.com'
        }
        return domain.lower() in public_domains

    async def generate_reports(self, intelligent_leads: List[LeadIntelligence]):
        """Generate intelligence reports and dashboards"""
        self.logger.info("📊 Phase 3: Report Generation")

        # Generate summary report
        await self.generate_summary_report(intelligent_leads)

        # Generate quality analysis
        await self.generate_quality_analysis(intelligent_leads)

        # Generate opportunity analysis
        await self.generate_opportunity_analysis(intelligent_leads)

        # Export to various formats
        await self.export_intelligence_data(intelligent_leads)

    async def generate_summary_report(self, leads: List[LeadIntelligence]):
        """Generate summary intelligence report"""
        report = {
            'timestamp': to_utc_iso8601(utc_now()),
            'total_leads': len(leads),
            'summary_stats': {
                'high_potential': len([l for l in leads if l.engagement_potential == 'high']),
                'medium_potential': len([l for l in leads if l.engagement_potential == 'medium']),
                'low_potential': len([l for l in leads if l.engagement_potential == 'low']),
                'with_email': len([l for l in leads if l.prospect.has_email()]),
                'with_company': len([l for l in leads if l.prospect.company]),
                'average_score': round(sum(l.intelligence_score for l in leads) / len(leads), 2) if leads else 0
            },
            'top_performers': [
                {
                    'login': lead.prospect.login,
                    'score': lead.intelligence_score,
                    'email': lead.prospect.get_best_email(),
                    'company': lead.prospect.company,
                    'engagement_potential': lead.engagement_potential
                }
                for lead in leads[:10]
            ]
        }

        report_file = Path(self.config.reporting_dir) / "dashboards" / f"intelligence_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        self.logger.info(f"📋 Summary report saved to {report_file}")

    async def generate_quality_analysis(self, leads: List[LeadIntelligence]):
        """Generate quality analysis report"""
        # Quality metrics analysis
        quality_metrics = {
            'email_coverage': len([l for l in leads if l.prospect.has_email()]) / len(leads) if leads else 0,
            'company_coverage': len([l for l in leads if l.prospect.company]) / len(leads) if leads else 0,
            'location_coverage': len([l for l in leads if l.prospect.location]) / len(leads) if leads else 0,
            'high_score_percentage': len([l for l in leads if l.intelligence_score >= 5.0]) / len(leads) if leads else 0
        }

        # Signal frequency analysis
        all_signals = []
        for lead in leads:
            all_signals.extend(lead.quality_signals)

        signal_counts = {}
        for signal in all_signals:
            signal_counts[signal] = signal_counts.get(signal, 0) + 1

        quality_report = {
            'timestamp': to_utc_iso8601(utc_now()),
            'quality_metrics': quality_metrics,
            'signal_frequency': dict(sorted(signal_counts.items(), key=lambda x: x[1], reverse=True)),
            'score_distribution': self._calculate_score_distribution(leads)
        }

        report_file = Path(self.config.analysis_dir) / "reports" / f"quality_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(quality_report, f, indent=2, default=str)

    async def generate_opportunity_analysis(self, leads: List[LeadIntelligence]):
        """Generate opportunity analysis report"""
        # Company analysis
        companies = {}
        for lead in leads:
            if lead.prospect.company:
                company = lead.prospect.company.strip().lstrip('@').lower()
            elif lead.prospect.company is not None:
                company = lead.prospect.company.lstrip('@').lower()
            else:
                continue

            if company not in companies:
                companies[company] = []
            companies[company].append({
                    'login': lead.prospect.login,
                    'score': lead.intelligence_score,
                    'email': lead.prospect.get_best_email()
                })

        # Technology analysis
        technologies = {}
        for lead in leads:
            if lead.prospect.language:
                tech = lead.prospect.language.lower()
                if tech not in technologies:
                    technologies[tech] = []
                technologies[tech].append({
                    'login': lead.prospect.login,
                    'score': lead.intelligence_score,
                    'company': lead.prospect.company
                })

        opportunity_report = {
            'timestamp': to_utc_iso8601(utc_now()),
            'company_clusters': {
                company: {
                    'lead_count': len(leads),
                    'avg_score': round(sum(l['score'] for l in leads) / len(leads), 2),
                    'leads': leads
                }
                for company, leads in companies.items()
                if len(leads) >= 2
            },
            'technology_clusters': {
                tech: {
                    'lead_count': len(leads),
                    'avg_score': round(sum(l['score'] for l in leads) / len(leads), 2),
                    'leads': leads
                }
                for tech, leads in technologies.items()
                if len(leads) >= 3
            }
        }

        report_file = Path(self.config.analysis_dir) / "reports" / f"opportunity_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w') as f:
            json.dump(opportunity_report, f, indent=2, default=str)

    def _calculate_score_distribution(self, leads: List[LeadIntelligence]) -> Dict[str, int]:
        """Calculate intelligence score distribution"""
        distribution = {'0-1': 0, '1-3': 0, '3-5': 0, '5+': 0}

        for lead in leads:
            score = lead.intelligence_score
            if score < 1:
                distribution['0-1'] += 1
            elif score < 3:
                distribution['1-3'] += 1
            elif score < 5:
                distribution['3-5'] += 1
            else:
                distribution['5+'] += 1

        return distribution

    async def export_intelligence_data(self, leads: List[LeadIntelligence]):
        """Export intelligence data in multiple formats"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # CSV Export
        csv_file = Path(self.config.reporting_dir) / "exports" / f"intelligent_leads_{timestamp}.csv"
        if leads:
            import csv
            with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=leads[0].to_dict().keys())
                writer.writeheader()
                for lead in leads:
                    writer.writerow(lead.to_dict())

        # JSON Export
        json_file = Path(self.config.reporting_dir) / "exports" / f"intelligent_leads_{timestamp}.json"
        with open(json_file, 'w') as f:
            json.dump([lead.to_dict() for lead in leads], f, indent=2, default=str)

        self.logger.info(f"💾 Exported intelligence data to {csv_file} and {json_file}")


def main():
    """Main entry point for the intelligence engine"""
    import argparse

    parser = argparse.ArgumentParser(description='Lead Intelligence Engine')
    parser.add_argument('--config', default='lead_intelligence/config/intelligence.yaml',
                       help='Intelligence configuration file')
    parser.add_argument('--github-token', help='GitHub API token')
    parser.add_argument('--base-config', default='config.yaml',
                       help='Base GitHub scraper configuration')
    parser.add_argument('--output-dir', default='lead_intelligence/data',
                       help='Output directory for intelligence data')

    args = parser.parse_args()

    # Load or create intelligence config
    if os.path.exists(args.config):
        with open(args.config, 'r') as f:
            config_data = yaml.safe_load(f)
    else:
        config_data = {}

    # Override with command line args (hardcoded token)
    github_token = args.github_token or os.environ.get('GITHUB_TOKEN', '')

    config = IntelligenceConfig(
        github_token=github_token,
        base_config_path=args.base_config,
        output_dir=args.output_dir
    )

    # Update config with loaded data
    for key, value in config_data.items():
        if hasattr(config, key):
            setattr(config, key, value)

    # Run intelligence engine
    engine = IntelligenceEngine(config)

    # Run async intelligence cycle
    async def run():
        await engine.run_intelligence_cycle()

    asyncio.run(run())


if __name__ == '__main__':
    main()
