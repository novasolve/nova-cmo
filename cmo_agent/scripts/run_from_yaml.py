#!/usr/bin/env python3
"""
Run CMO Agent using a small structured YAML config (no typed GOAL needed).

- Loads YAML (with params, pushed_since, goal_template, assistant_intro_template)
- Computes pushed_since if null using params.activity_days
- Renders templates with {{ }} (Jinja2 if available, fallback otherwise)
- Forwards a derived goal string to the existing run_agent entrypoint
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as _dt
import logging
from pathlib import Path
from typing import Any, Dict, Mapping

import yaml

# Ensure project root on sys.path for absolute imports
import sys
project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from cmo_agent.utils.templating import render_template
from cmo_agent.scripts.run_agent import run_campaign


logger = logging.getLogger(__name__)


def _parse_set_overrides(pairs: list[str] | None) -> Dict[str, str]:
    overrides: Dict[str, str] = {}
    if not pairs:
        return overrides
    for item in pairs:
        if not item:
            continue
        if "=" not in item:
            raise ValueError(f"Invalid override '{item}'. Use KEY=VALUE format.")
        key, value = item.split("=", 1)
        overrides[key.strip()] = value
    return overrides


def _apply_overrides(config: Dict[str, Any], overrides: Mapping[str, str]) -> Dict[str, Any]:
    if not overrides:
        return config
    params = config.get("params") or {}
    if not isinstance(params, dict):
        params = {}

    for key, value in overrides.items():
        if key.startswith("params."):
            params_key = key.split(".", 1)[1]
            params[params_key] = value
        elif key in ("pushed_since", "goal_template", "assistant_intro_template"):
            config[key] = value
        else:
            # Convenience: treat bare keys as params overrides
            params[key] = value

    config["params"] = params
    return config


def _compute_pushed_since(config: Dict[str, Any]) -> str:
    if isinstance(config.get("pushed_since"), str) and config["pushed_since"].strip():
        return config["pushed_since"].strip()
    params = config.get("params") or {}
    try:
        activity_days = int(params.get("activity_days", 90))
    except Exception:
        activity_days = 90
    date = (_dt.date.today() - _dt.timedelta(days=activity_days)).isoformat()
    return date


def _build_template_context(config: Dict[str, Any]) -> Dict[str, Any]:
    params = config.get("params") or {}
    # Flatten params into top-level, but also expose under 'params'
    context: Dict[str, Any] = {**params}
    context["params"] = dict(params)
    context["pushed_since"] = _compute_pushed_since(config)
    # Provide a lightweight job_id for banner rendering if needed
    context["job_id"] = f"local-{_dt.datetime.now().strftime('%Y%m%d-%H%M%S')}"
    return context


def _derive_goal(config: Dict[str, Any], context: Mapping[str, Any]) -> str:
    template = config.get("goal_template") or ""
    if not isinstance(template, str) or not template.strip():
        raise ValueError("goal_template is required in the YAML config")
    return " ".join(render_template(template, context).split())


async def _run_with_yaml(config_path: str, dry_run: bool, no_emoji: bool, interactive: bool, set_pairs: list[str] | None) -> int:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    with path.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
        if not isinstance(cfg, dict):
            raise ValueError("YAML root must be a mapping")

    # Apply inline overrides and compute context
    overrides = _parse_set_overrides(set_pairs)
    cfg = _apply_overrides(cfg, overrides)
    context = _build_template_context(cfg)

    # Render the human-friendly goal string
    goal = _derive_goal(cfg, context)

    # Forward to the existing runner (backward-compatible)
    result = await run_campaign(goal, config_path=config_path, dry_run=dry_run, no_emoji=no_emoji, interactive=interactive)
    return 0 if result.get("success", False) else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Run CMO Agent from YAML (no GOAL needed)")
    parser.add_argument("--config", "-c", required=True, help="Path to YAML config (ICP)")
    parser.add_argument("--dry-run", action="store_true", help="Run in dry-run mode (no sending)")
    parser.add_argument("--no-emoji", action="store_true", help="Disable emoji in CLI output")
    parser.add_argument("--interactive", action="store_true", help="Prompt to run another campaign after completion")
    parser.add_argument("--set", dest="set_pairs", nargs="+", help="Inline overrides as KEY=VALUE (e.g., language=Go target_leads=50)")
    args = parser.parse_args()

    exit_code = asyncio.run(_run_with_yaml(args.config, args.dry_run, args.no_emoji, args.interactive, args.set_pairs))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()


