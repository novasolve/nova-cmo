"""
Quick, non-destructive tests for RunState P0 features:
- state_version + migrate_run_state
- idempotency key generation
- checkpoint save/load with metadata
"""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime

from cmo_agent.core.state import (
    RunState,
    JobMetadata,
    migrate_run_state,
    save_checkpoint,
    load_latest_checkpoint,
    make_idempotency_key,
    DEFAULT_CONFIG,
)


def main() -> int:
    meta = JobMetadata(goal="RunState P0 smoke test", created_by="tester")

    # Create a minimal state missing many fields to validate migration
    raw_state = {
        "job_id": meta.job_id,
        "goal": meta.goal,
        "created_at": meta.created_at,
        "created_by": meta.created_by,
        # intentionally omitting most fields
    }

    print("[1] Migrating raw state → full RunState...")
    state: RunState = migrate_run_state(raw_state)
    assert state.get("state_version") is not None, "state_version not set by migration"
    assert isinstance(state.get("errors"), list), "errors should be a list"
    assert isinstance(state.get("checkpoints"), list), "checkpoints should be a list"
    assert isinstance(state.get("checkpoints_meta"), list), "checkpoints_meta should be a list"
    assert isinstance(state.get("idempotency_keys"), dict), "idempotency_keys should be a dict"
    print("    ✓ migration OK")

    print("[2] Creating idempotency key...")
    idem = make_idempotency_key(
        job_id=state["job_id"],
        stage="sending",
        target_identifier="jane@example.com",
        payload={"subject": "Hello", "body": "World"},
    )
    assert isinstance(idem, str) and len(idem) == 64, "idempotency key must be sha256 hex"
    state["idempotency_keys"]["jane@example.com"] = idem
    print(f"    ✓ idempotency={idem[:12]}... (64 hex)")

    print("[3] Saving checkpoint...")
    ckpt_path = save_checkpoint(state["job_id"], state, type="manual", reason="p0-test")
    print(f"    ✓ checkpoint saved: {ckpt_path}")

    print("[4] Loading latest checkpoint...")
    loaded = load_latest_checkpoint(state["job_id"])
    assert loaded is not None, "failed to load latest checkpoint"
    assert loaded.get("job_id") == state["job_id"], "job_id mismatch after load"
    print("    ✓ checkpoint load OK")

    # Show a brief summary
    summary = {
        "job_id": loaded.get("job_id"),
        "state_version": loaded.get("state_version"),
        "checkpoints_count": len(loaded.get("checkpoints", [])),
        "checkpoints_meta_count": len(loaded.get("checkpoints_meta", [])),
        "has_idempotency": len(loaded.get("idempotency_keys", {})) > 0,
    }
    print("[5] Summary:")
    print(json.dumps(summary, indent=2))

    print("All P0 RunState checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


