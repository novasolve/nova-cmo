#!/usr/bin/env python3
"""
CMO Agent Runner - Execute outbound campaigns
"""
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional

import yaml
from dotenv import load_dotenv

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

        # Load configuration
        config = load_config(config_path)
        logger.info(f"Loaded configuration from {config_path or 'defaults'}")
        # Reconfigure logging and monitoring according to loaded config
        _setup_logging_from_config(config)
        configure_metrics_from_config(config)

        # Validate required credentials early to avoid noisy retries
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
        result = await agent.run_job(goal)
        logger.info(f"Campaign completed: {result['success']}")

        # Print summary
        if result.get('success'):
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

            final_state = as_map(result.get('final_state'))
            report = as_map(result.get('report'))
            summary = as_map(report.get('summary'))
            counters = as_map(final_state.get('counters'))

            def to_int(value, default=0) -> int:
                try:
                    return int(value)
                except (TypeError, ValueError):
                    return int(default)

            leads_list = final_state.get('leads')
            leads_count = len(leads_list) if isinstance(leads_list, list) else 0
            to_send_list = final_state.get('to_send')
            to_send_count = len(to_send_list) if isinstance(to_send_list, list) else 0

            stats = {
                "steps": max(to_int(summary.get("steps_completed"), 0), to_int(counters.get("steps"), 0)),
                "api_calls": max(to_int(summary.get("api_calls_made"), 0), to_int(counters.get("api_calls"), 0)),
                "leads": max(to_int(summary.get("leads_processed"), 0), leads_count),
                "emails_prepared": max(to_int(summary.get("emails_prepared"), 0), to_send_count),
            }

            party = "🎉 " if not no_emoji else ""
            chart = "📊 " if not no_emoji else ""
            email_icon = "📧 " if not no_emoji else ""
            building = "🏢 " if not no_emoji else ""
            print(f"\n{party}Campaign completed successfully!")
            print(f"{chart}Stats: {stats}")
            print(f"{email_icon}Emails prepared: {stats['emails_prepared']}")

            reports = as_map(final_state.get("reports"))
            attio = reports.get("attio", {}) if isinstance(reports.get("attio", {}), dict) else {}
            synced_people = attio.get("synced_people", []) if isinstance(attio.get("synced_people", []), list) else []
            print(f"{building}CRM sync: {len(synced_people)}")

            # Optional interactive continuation
            if interactive:
                answer = input(("Run another campaign? (y/N): "))
                if answer.strip().lower() in ["y", "yes"]:
                    next_goal = input("Enter goal for next campaign: ")
                    return await run_campaign(next_goal, config_path=config_path, dry_run=dry_run, no_emoji=no_emoji, interactive=interactive)
        else:
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
