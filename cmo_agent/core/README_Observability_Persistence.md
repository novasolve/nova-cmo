## 8) Observability & Persistence

This document explains how the CMO Agent persists execution state and exposes operational visibility. It covers state checkpoints, job queue durability, artifacts, metrics, and how to configure and test the system.

### What you get

- Durable jobs with pause/resume and crash recovery
- Periodic and milestone checkpoints of `RunState`
- File‑backed persistent job queue
- Structured metrics and logs with alerting hooks
- Managed artifacts (CSV/JSON exports) with retention

---

### Data layout (defaults)

- State checkpoints: `./checkpoints/{job_id}_{type}_{timestamp}.json`
- Artifacts/exports: `./exports` and `./artifacts`
- Logs (your logger destination): `./logs` if configured

All paths are driven by `DEFAULT_CONFIG` in `cmo_agent/core/state.py` under `directories`:

```json
{
  "directories": {
    "exports": "./exports",
    "checkpoints": "./checkpoints",
    "logs": "./logs",
    "artifacts": "./artifacts"
  }
}
```

---

### RunState persistence & checkpoints

RunState is the single source of truth for a job. The agent reduces tool results into RunState and periodically checkpoints it to disk.

- Checkpoint file format: JSON with `{ job_id, checkpoint_type, timestamp, state }`
- Trigger policy (hybrid):
  - Time‑based (e.g., every 300s)
  - Step‑based (e.g., every 50 steps)
  - Volume‑based (e.g., every 1000 leads)
  - Stage transition and significant milestones
- Implementation: see `cmo_agent/agents/cmo_agent.py` → `_should_checkpoint` and `_save_checkpoint`
- State schema: `cmo_agent/core/state.py` → `RunState`

Resume behavior: on pause/crash, the latest checkpoint is used to resume without losing progress.

---

### Persistent job queue

`PersistentJobQueue` stores job metadata/status to disk so the queue survives restarts.

- Location: `cmo_agent/core/persistent_queue.py`
- Storage: JSON files in `./data/jobs/{job_id}.json`
- Capabilities: enqueue/dequeue, pause/resume/cancel, progress streaming, listing, and stats.

Useful scripts:

- `make test-queue` → exercises queue persistence
- `make test-persistence` → exercises execution engine with persistence

---

### Artifacts management

Artifacts (CSV exports, reports, debug payloads) are stored via `ArtifactManager`.

- Location: `cmo_agent/core/artifacts.py`
- Directories: `./exports` (reports/lists), `./artifacts` (logs/metrics/debug)
- Features: metadata registry, optional compression, retention policies, cleanup task, storage optimization

Common artifact types: `repositories`, `candidates`, `leads`, `personalization`, `reports`, `logs`, `metrics`, `debug`.

---

### Metrics, logging, and alerts

Structured operational metrics and logs are produced by `monitoring.py`.

- Location: `cmo_agent/core/monitoring.py`
- Components:
  - `MetricsCollector` → aggregates job/queue/API/resource/error/checkpoint/business metrics
  - `StructuredLogger` → emits structured log events with correlation IDs
  - `MetricsLogger` → periodic snapshot logging and basic alerting (error‑rate, queue depth, memory, worker crashes, API success‑rate)

Recommended metrics to watch:

- Throughput, queue depth, job durations (avg/median/p95)
- API call totals/success and rate‑limit hits
- Error rate by component/type; critical errors
- Leads processed/enriched; repos discovered; emails sent

Optional tracing (future/optional): integrate Langfuse to trace each tool call with tags `{job_id, stage, repo_count}`.

---

### Configuration

Primary knobs live in `DEFAULT_CONFIG` in `cmo_agent/core/state.py` and can be overridden at runtime/config files:

- `directories.exports`, `directories.checkpoints`, `directories.logs`, `directories.artifacts`
- `job_config.checkpoints`: `{ time_interval, step_interval, volume_interval }`
- `rate_limits`, `timeouts`, `retries`, `error_handling`

Environment and YAML examples are in `cmo_agent/config/*.yaml`. For quick edits, adjust `directories` and checkpoint intervals.

---

### How to run and test

Quick smoke:

```bash
cd cmo_agent
python scripts/test_execution_engine.py
```

Run engine and start workers:

```bash
cd cmo_agent
python scripts/run_execution.py --job "Find 2000 Python maintainers" --start-workers
```

Queue/persistence checks:

```bash
cd cmo_agent
make test-queue
make test-persistence
```

After a run, inspect:

- Checkpoints: `ls checkpoints/` and open the latest JSON
- Artifacts: `ls exports/` or `ls artifacts/` and inspect files
- Logs/metrics: your configured logger output; look for "Metrics snapshot collected"

---

### Troubleshooting

- No checkpoints written: verify `directories.checkpoints` exists and that `_should_checkpoint` thresholds are reachable for your run size.
- Resume didn’t pick up latest state: ensure the job’s `job_id` matches the checkpoint files; confirm `_save_checkpoint` succeeds in logs.
- Queue progress not updating: check `data/jobs/*.json` and the progress stream; ensure job status transitions are persisted.
- Artifacts missing: confirm `ArtifactManager` initialized with config, and that the process has write permissions to `exports`/`artifacts`.
- High error rate or rate‑limits: watch alerts in logs, tune `retries`, `rate_limits`, and consider widening intervals.

---

### References

- `cmo_agent/core/state.py` (RunState, DEFAULT_CONFIG)
- `cmo_agent/agents/cmo_agent.py` (checkpoint logic)
- `cmo_agent/core/persistent_queue.py` (durable queue)
- `cmo_agent/core/artifacts.py` (artifacts & retention)
- `cmo_agent/core/monitoring.py` (metrics & structured logs)
