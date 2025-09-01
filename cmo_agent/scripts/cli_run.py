#!/usr/bin/env python3
"""
Phase 0: CLI that uses the same API path as Web UI
Makes CLI call /api/jobs and stream SSE events for unified behavior
"""
import asyncio
import json
import sys
import time
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import aiohttp
from tqdm import tqdm
import argparse
from datetime import datetime, timedelta, date

# Add parent directory to path
parent_dir = str(Path(__file__).parent.parent)
sys.path.insert(0, parent_dir)


class CLIRenderer:
    """Renders job events for CLI with pretty TTY output"""
    
    def __init__(self, no_emoji: bool = False):
        self.no_emoji = no_emoji
        self.start_time = time.time()
        self._pbar: Optional[tqdm] = None
        self._last_step: Optional[int] = None
        self._total_steps: Optional[int] = None
        
    def render_event(self, event_data: Dict[str, Any]):
        """Render a single job event"""
        event_type = event_data.get('type', 'unknown')
        data = event_data.get('data', {})
        
        if event_type == 'job.started':
            print(f"🚀 Job started: {data.get('job_id', 'unknown')}")
            # Initialize progress bar lazily
            if self._pbar is None:
                self._total_steps = data.get('total_steps') or None
                self._pbar = tqdm(total=self._total_steps, unit="step", dynamic_ncols=True)
                self._pbar.set_description("Running")
        elif event_type == 'tool.started':
            tool_name = data.get('tool_name', 'unknown')
            print(f"🔧 Executing: {tool_name}")
        elif event_type == 'progress':
            stage = data.get('stage', 'unknown')
            current_item = data.get('current_item', '')
            # Initialize progress bar if not yet created
            if self._pbar is None:
                self._total_steps = data.get('total_steps') or None
                self._pbar = tqdm(total=self._total_steps, unit="step", dynamic_ncols=True)
                self._pbar.set_description("Running")

            # Update bar on step changes; do not regress
            step = data.get('step')
            if isinstance(step, int):
                if self._last_step is None:
                    self._pbar.n = max(0, step)
                    self._pbar.refresh()
                elif step > self._last_step:
                    self._pbar.update(step - self._last_step)
                self._last_step = step

            # Update postfix/status
            postfix = {}
            if isinstance(stage, str) and stage not in (None, '', 'unknown'):
                postfix['stage'] = stage
            if isinstance(current_item, str) and current_item:
                postfix['item'] = current_item
            metrics = data.get('metrics') or {}
            if isinstance(metrics, dict) and metrics.get('repos'):
                postfix['repos'] = metrics['repos']
            if postfix:
                try:
                    self._pbar.set_postfix(postfix, refresh=False)
                except Exception:
                    pass
            else:
                # Fallback to a simple line when no postfix
                print(f"📊 {stage}: {current_item}")
        elif event_type == 'job.completed':
            duration = time.time() - self.start_time
            print(f"✅ Job completed in {duration:.1f}s")
            if self._pbar is not None:
                try:
                    # If total known and not reached, close gracefully
                    if self._total_steps is not None and self._last_step is not None and self._last_step < self._total_steps:
                        self._pbar.n = self._total_steps
                        self._pbar.refresh()
                    self._pbar.close()
                except Exception:
                    pass
        elif event_type == 'error':
            print(f"❌ Error: {data.get('message', 'Unknown error')}")
            if self._pbar is not None:
                try:
                    self._pbar.close()
                except Exception:
                    pass


def _parse_yaml_config(config_path: str, set_pairs: Optional[list] = None) -> Dict[str, Any]:
    """Parse YAML config and apply overrides"""
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


def _build_job_spec_from_yaml(config: Dict[str, Any]) -> Dict[str, Any]:
    """Build JobSpec from YAML config (Phase 0: use dict, Phase 1: use dataclass)"""
    params = config.get('params', {})
    
    # Compute pushed_since date
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
        # Synthesize goal
        language = params.get('language', 'Python')
        stars_range = params.get('stars_range', '300..2000')
        activity_days = params.get('activity_days', 90)
        goal = f"Find maintainers of {language} repos stars:{stars_range} pushed:>={pushed_since}; prioritize active {activity_days} days; export CSV."
    
    return {
        "goal": goal,
        "metadata": {
            "created_by": "cli_unified",
            "autopilot_level": params.get('autopilot_level', 2),
            "budget_per_day": params.get('budget_per_day', 10),
            "config_source": "yaml",
            "target_leads": params.get('target_leads', 20)
        }
    }


async def run_job_via_api(job_spec: Dict[str, Any], api_base: str = "http://localhost:8000") -> bool:
    """Run job via API and stream events (Phase 0 implementation)"""
    renderer = CLIRenderer()
    
    async with aiohttp.ClientSession() as session:
        try:
            # Submit job
            print(f"🎯 Goal: {job_spec['goal']}")
            print("📡 Submitting job to API...")
            
            async with session.post(
                f"{api_base}/api/jobs",
                json=job_spec,
                headers={"Content-Type": "application/json"}
            ) as resp:
                if not resp.ok:
                    error_text = await resp.text()
                    print("❌ Job submission failed")
                    print(f"   URL: {api_base}/api/jobs")
                    print(f"   Status: {resp.status} {resp.reason}")
                    print(f"   Body: {error_text[:2000]}")
                    print("   Tip: ensure the backend is running (./dev.sh) and the payload is valid.")
                    return False
                
                job_result = await resp.json()
                job_id = job_result.get('id')
                print(f"✅ Job submitted: {job_id}")
        
            # Stream events
            print("📺 Streaming job events...")
            async with session.get(f"{api_base}/api/jobs/{job_id}/events") as resp:
                if resp.ok:
                    async for line in resp.content:
                        if line:
                            try:
                                # Parse SSE format
                                line_str = line.decode('utf-8').strip()
                                if line_str.startswith('data: '):
                                    event_json = line_str[6:]  # Remove 'data: ' prefix
                                    event = json.loads(event_json)
                                    renderer.render_event(event)
                            except json.JSONDecodeError:
                                pass  # Skip malformed events
                            except Exception as e:
                                print(f"⚠️ Event parsing error: {e}")
            
            # Get final summary and persist locally
            print("\n📋 Fetching campaign summary...")
            async with session.get(f"{api_base}/api/jobs/{job_id}/summary") as resp:
                if resp.ok:
                    summary = await resp.json()
                    print("\n" + "="*60)
                    print("📋 CAMPAIGN SUMMARY")
                    print("="*60)
                    print(json.dumps(summary, indent=2))
                    print("="*60)

                    # Persist summary and any available leads/metrics locally under ./exports
                    try:
                        exports_dir = Path("./exports")
                        exports_dir.mkdir(parents=True, exist_ok=True)

                        # Save raw summary JSON
                        summary_path = exports_dir / f"{job_id}_summary.json"
                        with open(summary_path, 'w', encoding='utf-8') as f:
                            json.dump(summary, f, indent=2, default=str)
                        print(f"💾 Saved summary: {summary_path}")

                        # Mirror metrics artifact locally (best-effort)
                        try:
                            artifacts = summary.get('artifacts') or []
                            metrics_art = None
                            for a in artifacts:
                                if isinstance(a, dict) and a.get('type') in ('performance_metrics', 'metrics'):
                                    metrics_art = a
                                    break

                            # Build minimal metrics content from summary
                            metrics_payload = {
                                'job_id': job_id,
                                'source': 'cli_mirror',
                                'export_timestamp': datetime.now().isoformat(),
                                'status': summary.get('status'),
                                'summary': summary.get('summary') or {},
                            }

                            metrics_filename = (
                                (metrics_art or {}).get('filename')
                                or f"{job_id}_metrics.json"
                            )
                            metrics_path = exports_dir / metrics_filename
                            with open(metrics_path, 'w', encoding='utf-8') as f:
                                json.dump(metrics_payload, f, indent=2, default=str)
                            print(f"💾 Saved metrics: {metrics_path}")
                        except Exception as e:
                            print(f"⚠️ Failed to mirror metrics: {e}")

                        # Attempt to extract leads from summary and save CSV/JSON locally
                        state = (
                            summary.get('final_state')
                            or summary.get('agent')
                            or summary.get('state')
                            or {}
                        )
                        leads = state.get('leads') if isinstance(state, dict) else None
                        if isinstance(leads, list) and leads:
                            # JSON export
                            leads_json_path = exports_dir / f"{job_id}_leads.json"
                            with open(leads_json_path, 'w', encoding='utf-8') as f:
                                json.dump({
                                    'job_id': job_id,
                                    'export_timestamp': datetime.now().isoformat(),
                                    'data_type': 'leads',
                                    'count': len(leads),
                                    'leads': leads,
                                }, f, indent=2, default=str)
                            print(f"💾 Saved leads JSON: {leads_json_path}")

                            # CSV export (union headers)
                            headers = set()
                            for row in leads:
                                if isinstance(row, dict):
                                    headers.update(row.keys())
                            headers = sorted(list(headers))
                            leads_csv_path = exports_dir / f"{job_id}_leads.csv"
                            import csv as _csv
                            with open(leads_csv_path, 'w', newline='', encoding='utf-8') as f:
                                writer = _csv.DictWriter(f, fieldnames=headers)
                                writer.writeheader()
                                for row in leads:
                                    if isinstance(row, dict):
                                        writer.writerow({k: row.get(k, '') for k in headers})
                            print(f"💾 Saved leads CSV: {leads_csv_path}")
                        else:
                            print("ℹ️ No leads found in summary state; saved summary only.")
                    except Exception as e:
                        print(f"⚠️ Failed to persist local exports: {e}")
                else:
                    body = await resp.text()
                    print("⚠️ Could not fetch summary")
                    print(f"   URL: {api_base}/api/jobs/{job_id}/summary")
                    print(f"   Status: {resp.status} {resp.reason}")
                    print(f"   Body: {body[:2000]}")
            
            return True
            
        except aiohttp.ClientError as e:
            print(f"❌ API connection failed: {e}")
            print("💡 Make sure the API server is running: ./dev.sh")
            return False
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return False


async def main():
    """CLI entry point that uses unified API path"""
    parser = argparse.ArgumentParser(description="CMO Agent CLI - Unified API Path")
    parser.add_argument("--config", "-c", required=True, help="Path to YAML config file")
    parser.add_argument("--set", action="append", help="Override config params (e.g., --set language=Go)")
    parser.add_argument("--api-base", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    
    args = parser.parse_args()
    
    try:
        # Parse config
        config = _parse_yaml_config(args.config, args.set)
        
        # Build job spec
        job_spec = _build_job_spec_from_yaml(config)
        
        if args.dry_run:
            job_spec["metadata"]["dry_run"] = True
            job_spec["goal"] += " (DRY RUN)"
        
        print("🚀 CMO Agent CLI - Unified Path")
        print("="*60)
        
        # Run via API
        success = await run_job_via_api(job_spec, args.api_base)
        
        if success:
            print("\n🎉 Campaign completed successfully!")
        else:
            print("\n💥 Campaign failed!")
            sys.exit(1)
            
    except Exception as e:
        print(f"💥 CLI error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
