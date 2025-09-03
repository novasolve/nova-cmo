#!/usr/bin/env python3
# scripts/log_rescue.py
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

LEDGER = Path("artifacts/rescue_ledger.jsonl")


def log_event(event: str, **data):
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "event": event,
        **data,
    }
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main():
    # CLI usage: python scripts/log_rescue.py event key=value ...
    if len(sys.argv) < 2:
        print("Usage: log_rescue.py <event> key=value [key=value...]")
        sys.exit(1)
    event = sys.argv[1]
    extra = {}
    for kv in sys.argv[2:]:
        if "=" in kv:
            k, v = kv.split("=", 1)
            # coerce ints when possible
            if v.isdigit():
                extra[k] = int(v)
            else:
                extra[k] = v
    log_event(event, **extra)


if __name__ == "__main__":
    main()
