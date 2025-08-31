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

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('./logs/cmo_agent.log', mode='a')
    ]
)
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


async def run_campaign(goal: str, config_path: Optional[str] = None):
    """Run a CMO Agent campaign"""
    try:
        logger.info(f"Starting CMO Agent campaign: {goal}")

        # Load configuration
        config = load_config(config_path)
        logger.info(f"Loaded configuration from {config_path or 'defaults'}")

        # Initialize agent
        agent = CMOAgent(config)
        logger.info("CMO Agent initialized successfully")

        # Run the job
        result = await agent.run_job(goal)
        logger.info(f"Campaign completed: {result['success']}")

        # Print summary
        if result.get('success'):
            final_state = result.get('final_state') or {}
            report = result.get('report') or {}
            # Prefer summary from final report when available
            summary = report.get('summary', {}) if isinstance(report, dict) else {}
            counters = final_state.get('counters', {}) if isinstance(final_state, dict) else {}
            stats = {
                "steps": summary.get("steps_completed") or counters.get("steps", 0),
                "api_calls": summary.get("api_calls_made") or counters.get("api_calls", 0),
                "leads": summary.get("leads_processed") or (len(final_state.get("leads", [])) if isinstance(final_state.get("leads", []), list) else 0),
                "emails_prepared": summary.get("emails_prepared") or (len(final_state.get("to_send", [])) if isinstance(final_state.get("to_send", []), list) else 0),
            }

            print("\n🎉 Campaign completed successfully!")
            print(f"📊 Stats: {stats}")
            print(f"📧 Emails prepared: {stats['emails_prepared']}")

            reports = final_state.get("reports", {}) if isinstance(final_state.get("reports", {}), dict) else {}
            attio = reports.get("attio", {}) if isinstance(reports.get("attio", {}), dict) else {}
            synced_people = attio.get("synced_people", []) if isinstance(attio.get("synced_people", []), list) else []
            print(f"🏢 CRM sync: {len(synced_people)}")
        else:
            print(f"\n❌ Campaign failed: {result.get('error', 'Unknown error')}")

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

    args = parser.parse_args()

    # Modify goal for dry-run
    if args.dry_run:
        args.goal += " (DRY RUN - no actual sending)"

    # Ensure log directory exists
    Path("./logs").mkdir(exist_ok=True)

    # Run the campaign
    result = asyncio.run(run_campaign(args.goal, args.config))

    # Exit with appropriate code
    sys.exit(0 if result.get('success', False) else 1)


if __name__ == "__main__":
    main()
