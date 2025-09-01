#!/usr/bin/env python3
"""
Unified CLI - Phase 1 Implementation
Single entry point with both in-process and API modes
"""
import asyncio
import argparse
import sys
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, date

# Add parent directory to path
parent_dir = str(Path(__file__).parent.parent)
sys.path.insert(0, parent_dir)

from engine.types import JobSpec, RunSummary
from engine.events import CLIRenderer, SummaryCollector

# Optional import: only needed for in-process mode. Avoid import errors when
# using --mode api on footprints that don't include the inproc engine.
try:  # pragma: no cover
    from engine.core import create_unified_engine  # type: ignore
except Exception:  # Lazy-import inside run_inproc_mode if needed
    create_unified_engine = None  # type: ignore


def _parse_yaml_config(config_path: str, set_pairs: Optional[List[str]] = None) -> Dict[str, Any]:
    """Parse YAML config and apply SET overrides"""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
        
    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
        
    # Apply SET overrides
    if set_pairs:
        params = cfg.get('params', {})
        for pair in set_pairs:
            if '=' in pair:
                key, value = pair.split('=', 1)
                # Try to parse as int/float, fallback to string
                try:
                    if '.' in value:
                        value = float(value)
                    else:
                        value = int(value)
                except ValueError:
                    pass
                params[key] = value
        cfg['params'] = params
    
    return cfg


def _build_job_spec_from_yaml(config: Dict[str, Any]) -> JobSpec:
    """Build JobSpec from YAML config"""
    params = config.get('params', {})
    
    # Compute pushed_since date (consistent with CLI)
    pushed_since = config.get('pushed_since')
    if not pushed_since:
        activity_days = int(params.get('activity_days', 90))
        pushed_since = (date.today() - timedelta(days=activity_days)).isoformat()
    
    # Build goal from template or synthesize
    template = config.get('goal_template')
    if template:
        goal = template.replace('{{language}}', params.get('language', 'Python'))
        goal = goal.replace('{{stars_range}}', params.get('stars_range', '300..2000'))
        goal = goal.replace('{{pushed_since}}', pushed_since)
        goal = goal.replace('{{activity_days}}', str(params.get('activity_days', 90)))
    else:
        # Synthesize goal (same logic as original CLI)
        language = params.get('language', 'Python')
        stars_range = params.get('stars_range', '300..2000')
        activity_days = params.get('activity_days', 90)
        goal = f"Find maintainers of {language} repos stars:{stars_range} pushed:>={pushed_since}; prioritize active {activity_days} days; export CSV."
    
    return JobSpec(
        goal=goal,
        budget_usd=float(params.get('budget_per_day', 10)),
        autopilot_level=int(params.get('autopilot_level', 2)),
        target_leads=params.get('target_leads'),
        target_emails=params.get('target_emails'),
        created_by="unified_cli",
        constraints={
            'language': params.get('language', 'Python'),
            'stars_range': params.get('stars_range', '300..2000'),
            'activity_days': params.get('activity_days', 90)
        }
    )


async def run_inproc_mode(spec: JobSpec, no_emoji: bool = False) -> RunSummary:
    """Run in-process for CLI speed"""
    print("🚀 CMO Agent - In-Process Mode")
    print("="*60)
    print(f"🎯 Goal: {spec.goal}")
    print(f"💰 Budget: ${spec.budget_usd}")
    print(f"🤖 Autonomy: L{spec.autopilot_level}")
    
    # Create unified engine (lazy import here to support API-only usage)
    global create_unified_engine  # type: ignore
    if create_unified_engine is None:  # type: ignore
        from engine.core import create_unified_engine as _mk_engine  # type: ignore
        create_unified_engine = _mk_engine  # type: ignore
    engine = create_unified_engine()  # type: ignore
    
    # Create CLI sinks
    sinks = engine.create_cli_sinks(no_emoji=no_emoji)
    
    # Run in-process
    summary = await engine.run_inproc(spec, sinks)
    
    return summary


async def run_api_mode(spec: JobSpec, api_base: str = "http://localhost:8000") -> bool:
    """Run via API (fallback to Phase 0 implementation)"""
    # Import the Phase 0 implementation
    from .cli_run import run_job_via_api
    
    job_data = spec.to_dict()
    return await run_job_via_api(job_data, api_base)


async def main():
    """Unified CLI entry point"""
    parser = argparse.ArgumentParser(description="CMO Agent - Unified CLI")
    parser.add_argument("--config", "-c", required=True, help="Path to YAML config file")
    parser.add_argument("--set", action="append", help="Override config params (e.g., --set language=Go)")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    parser.add_argument("--no-emoji", action="store_true", help="Disable emoji output")
    parser.add_argument("--mode", choices=["inproc", "api", "auto"], default="auto", 
                       help="Execution mode: inproc (fast), api (via server), auto (detect)")
    parser.add_argument("--api-base", default="http://localhost:8000", help="API base URL")
    
    args = parser.parse_args()
    
    try:
        # Parse config and build spec
        config = _parse_yaml_config(args.config, args.set)
        spec = _build_job_spec_from_yaml(config)
        
        if args.dry_run:
            spec.dry_run = True
            spec.goal += " (DRY RUN)"
        
        # Determine execution mode
        mode = args.mode
        if mode == "auto":
            # Try API first, fallback to in-process with clear diagnostics
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(f"{args.api_base}/api/jobs", timeout=2) as resp:
                        if resp.ok:
                            mode = "api"
                        else:
                            print(
                                f"ℹ️  API probe at {args.api_base}/api/jobs returned "
                                f"{resp.status} {resp.reason}; falling back to inproc."
                            )
                            mode = "inproc"
            except Exception as probe_err:
                print(
                    f"ℹ️  API not reachable at {args.api_base} ({probe_err}); "
                    "falling back to inproc."
                )
                mode = "inproc"
        
        print(f"🔧 Mode: {mode}")
        if mode == "api":
            # Brief disclaimer so users know what API mode means
            print(
                "ℹ️  API mode runs the job on the backend server and streams progress.\n"
                "   Final artifacts live on the server; this CLI will fetch the summary\n"
                "   and mirror key files into ./exports after completion."
            )
        
        # Execute based on mode
        if mode == "inproc":
            summary = await run_inproc_mode(spec, args.no_emoji)
            success = summary.ok
            
            if success:
                print(f"\n🎉 Campaign completed successfully!")
                print(f"📊 Results: {summary.stats}")
            else:
                print(f"\n💥 Campaign failed!")
                for error in summary.errors:
                    print(f"❌ {error}")
                    
        else:  # api mode
            success = await run_api_mode(spec, args.api_base)
        
        sys.exit(0 if success else 1)
        
    except FileNotFoundError as e:
        print(f"💥 Config error: {e}")
        print("   Tip: pass --config with a valid YAML file.")
    except Exception as e:
        print(f"💥 CLI error: {e}")
        print("   Tip: run with --mode api if the in-process engine isn't available,\n"
              "        or ensure backend is running with ./dev.sh when using API mode.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
