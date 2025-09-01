#!/usr/bin/env python3
"""
CMO Agent UX CLI

Renders high-level UX views backed by RunState checkpoints.
This is a read-only interface safe to run without external APIs.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def _ensure_rich_installed():
    try:
        import rich  # noqa: F401
    except Exception as e:  # pragma: no cover
        print(
            "rich is required for the UX CLI. Install with: pip install rich",
            file=sys.stderr,
        )
        raise


_ensure_rich_installed()
from rich.table import Table  # type: ignore  # noqa: E402
from rich.console import Console  # type: ignore  # noqa: E402
from rich.panel import Panel  # type: ignore  # noqa: E402
from rich.text import Text  # type: ignore  # noqa: E402
from rich.align import Align  # type: ignore  # noqa: E402

from .state_loader import load_latest_state


console = Console()


def _fmt_ts(ts: Optional[str]) -> str:
    if not ts:
        return "-"
    try:
        # Show friendly local time with ISO base
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ts


def view_dashboard(state: Dict[str, Any]) -> None:
    counters = state.get("counters", {}) or {}
    status = state.get("current_stage", "-")
    paused = state.get("paused", False)
    goal = state.get("goal", "-")
    reports = state.get("reports", {}) or {}

    top = Table.grid(expand=True)
    top.add_column(justify="left")
    top.add_column(justify="right")
    top.add_row(
        Text(f"Campaign: {goal}", style="bold"),
        Text(f"Status: {status}", style="bold cyan"),
    )
    console.print(Panel(top, title="Dashboard", border_style="green"))

    metrics = Table(title="Funnel", expand=True)
    metrics.add_column("Repos", justify="right")
    metrics.add_column("Candidates", justify="right")
    metrics.add_column("Leads", justify="right")
    metrics.add_column("To Send", justify="right")
    metrics.add_column("Errors", justify="right")

    repos = len(state.get("repos", []) or [])
    candidates = len(state.get("candidates", []) or [])
    leads = len(state.get("leads", []) or [])
    to_send = len(state.get("to_send", []) or [])
    errors = len(state.get("errors", []) or [])
    metrics.add_row(str(repos), str(candidates), str(leads), str(to_send), str(errors))
    console.print(metrics)

    info = Table(title="Run Info", expand=True)
    info.add_column("Job ID")
    info.add_column("Created")
    info.add_column("Updated")
    info.add_column("Paused")
    info.add_row(
        state.get("job_id", "-"),
        _fmt_ts(state.get("created_at")),
        _fmt_ts(state.get("completed_at")),
        "Yes" if paused else "No",
    )
    console.print(info)


def view_triage(state: Dict[str, Any]) -> None:
    # 3 columns: discovery, enrichment, hygiene (show counts and some items)
    discovery = state.get("repos", []) or []
    candidates = state.get("candidates", []) or []
    leads = state.get("leads", []) or []

    t = Table(title="Triage Board (Discovery → Enrichment → Hygiene)", expand=True)
    t.add_column("Discovery (repos)")
    t.add_column("Enrichment (candidates)")
    t.add_column("Hygiene (leads)")

    max_rows = max(len(discovery), len(candidates), len(leads), 3)
    for i in range(max_rows):
        d = discovery[i]["full_name"] if i < len(discovery) and discovery[i].get("full_name") else ""
        c = candidates[i]["login"] if i < len(candidates) and candidates[i].get("login") else ""
        h = leads[i]["email"] if i < len(leads) and leads[i].get("email") else ""
        t.add_row(d, c, h)
    console.print(t)


def view_personalization(state: Dict[str, Any]) -> None:
    to_send = state.get("to_send", []) or []
    t = Table(title="Personalization Review", expand=True)
    t.add_column("Lead")
    t.add_column("Subject")
    t.add_column("Confidence", justify="right")

    for row in to_send[:20]:
        lead = row.get("email") or row.get("login") or "-"
        subject = (row.get("subject") or "").strip()[:80]
        conf = row.get("confidence")
        t.add_row(str(lead), subject, f"{conf:.2f}" if isinstance(conf, (int, float)) else "-")
    console.print(t)


def view_queue(state: Dict[str, Any]) -> None:
    reports = state.get("reports", {}) or {}
    sends = reports.get("instantly", {}).get("sends", []) if isinstance(reports, dict) else []
    t = Table(title="Queue & Sending", expand=True)
    t.add_column("Email")
    t.add_column("Status")
    t.add_column("Timestamp")
    for s in sends[:50]:
        console_status = s.get("status", "-")
        console_ts = _fmt_ts(s.get("timestamp"))
        t.add_row(s.get("email", "-"), console_status, console_ts)
    console.print(t)


def view_sync(state: Dict[str, Any]) -> None:
    reports = state.get("reports", {}) or {}
    sync = reports.get("crm", []) if isinstance(reports, dict) else []
    t = Table(title="CRM Sync Log", expand=True)
    t.add_column("Lead")
    t.add_column("Operation")
    t.add_column("Match Key")
    t.add_column("Result")
    for r in sync[:50]:
        t.add_row(
            r.get("lead_id", "-"),
            r.get("operation", "-"),
            r.get("match_key", "-"),
            r.get("result", "-"),
        )
    console.print(t)


def view_issues(state: Dict[str, Any]) -> None:
    errors = state.get("errors", []) or []
    t = Table(title="Issues (Errors & Follow-ups)", expand=True)
    t.add_column("When")
    t.add_column("Tool")
    t.add_column("Severity")
    t.add_column("Message")
    for e in errors[:50]:
        t.add_row(
            _fmt_ts(e.get("timestamp")),
            str(e.get("tool", "-")),
            str(e.get("severity", "-")),
            str(e.get("human_readable", e.get("error", "-")))[:120],
        )
    console.print(t)


def render_view(name: str, state: Dict[str, Any]) -> None:
    name = name.lower()
    if name in ("dash", "dashboard"):
        view_dashboard(state)
    elif name in ("triage",):
        view_triage(state)
    elif name in ("perso", "personalization"):
        view_personalization(state)
    elif name in ("queue", "sending"):
        view_queue(state)
    elif name in ("sync",):
        view_sync(state)
    elif name in ("issues", "errors"):
        view_issues(state)
    elif name in ("all", "full"):
        view_dashboard(state)
        view_triage(state)
        view_personalization(state)
        view_queue(state)
        view_sync(state)
        view_issues(state)
    else:
        console.print(f"Unknown view: {name}", style="red")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="CMO Agent UX CLI (read-only)")
    parser.add_argument("view", nargs="?", default="dashboard", help="View name: dashboard|triage|personalization|queue|sync|issues|all")
    parser.add_argument("--dir", dest="dirs", action="append", help="Checkpoint directory (can be passed multiple times)")
    args = parser.parse_args(argv)

    loaded = load_latest_state(args.dirs)
    if not loaded:
        console.print("No checkpoint found. Run a campaign or ensure checkpoints exist.", style="yellow")
        return 1

    console.print(Panel(f"Loaded: {loaded.path}", title="Checkpoint", border_style="blue"))
    render_view(args.view, loaded.state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
