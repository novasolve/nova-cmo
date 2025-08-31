"""
Lightweight analytics emitter for CMO Agent UX events.

Writes JSONL events to logs/product_events.jsonl to avoid external dependencies.
This can later be swapped for your preferred analytics sink.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional


EVENT_LOG_PATH = Path("./logs/product_events.jsonl")


def _ensure_log_dir():
    try:
        EVENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


@dataclass
class AnalyticsEvent:
    event: str
    props: Dict[str, Any]
    timestamp: str


def emit(event: str, props: Optional[Dict[str, Any]] = None) -> None:
    _ensure_log_dir()
    payload = AnalyticsEvent(
        event=event,
        props=props or {},
        timestamp=datetime.utcnow().isoformat() + "Z",
    )
    try:
        with EVENT_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(payload)) + "\n")
    except Exception:
        # Best-effort; do not crash the caller
        pass


