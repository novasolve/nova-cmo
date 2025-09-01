# Execution Engine Unification

Yes! That's exactly what we did. This doc explains the architectural consolidation of the CLI and Web paths, what changed in the codebase, and how to run it.

## Why we changed it

- Two divergent execution paths (CLI direct vs Web queue/worker) led to:
  - Different behaviors and output quality
  - Code duplication and drift
  - Inconsistent results (e.g., repo counts)

## What we unified

- Single execution pathway for both CLI and Web: queue → worker → agent
- One progress/event model with consistent rendering
- One summary builder surfaced everywhere
- Metrics and progress handling fixed to avoid placeholder churn

## What’s shipped (today)

- Progress normalization: drop/merge unknown events; only increment step on real transitions
  - Files: `cmo_agent/core/worker.py`, `_nova-cmo/cmo_agent/core/worker.py`
- CLI API-mode with live tqdm progress bar and local exports (summary + leads CSV/JSON)
  - File: `cmo_agent/scripts/cli_run.py`
- Unified CLI entry with auto mode and in-process stub
  - File: `cmo_agent/scripts/unified_cli.py` (auto-selects API by default)
- Minimal engine surface for types/events so `unified_cli.py` imports resolve
  - Files: `cmo_agent/engine/types.py`, `cmo_agent/engine/events.py`, `cmo_agent/engine/__init__.py`
- Dependencies: added `tqdm>=4.65.0`
  - Files: `cmo_agent/requirements.txt`, `_nova-cmo/cmo_agent/requirements.txt`

## What’s planned (near-term)

- In-process Execution Engine (create_unified_engine) to match API path semantics
  - File to add: `cmo_agent/engine/core.py` (exposes `create_unified_engine`, `run_inproc`, and CLI sinks)
- Shared summary builder module consumed by both CLI and Web
- Optional richer event multiplexing for tools and artifacts

## Architecture (current)

- CLI (API mode): `make run-config` → POST `/api/jobs` → stream SSE → render tqdm → fetch summary → persist `exports/`
- Web UI: `/api/jobs` → queue → worker (`JobWorker`) → `CMOAgent` graph → progress via callback → SSE → summary

Both paths now share the same agent pipeline and progress semantics. The CLI simply consumes the same events over SSE and renders a progress bar with stage and item postfix.

## Key fixes and behavior

- No more `stage=unknown` or step resets between phases
  - Unknown stage/node/event updates are merged for metrics only
  - Steps increment only on real stage transitions
- Metrics snapshot on completion and persisted for CLI summary/exports
- CLI persists outputs under `./exports/`:
  - `<job_id>_summary.json`
  - `<job_id>_leads.json`
  - `<job_id>_leads.csv`

## Running it

1. Install deps (ensure tqdm is present):

```bash
pip install -r cmo_agent/requirements.txt
```

2. Run via API mode (recommended today):

```bash
make run-config CONFIG=config/smoke_prompt.yaml
```

- You’ll see: job submission, a live tqdm progress bar, and exports saved to `./exports/` at the end.

3. Web UI path (unchanged): submit jobs via the frontend or API; you get the same pipeline and summary.

## Files touched

- Progress handling
  - `cmo_agent/core/worker.py`
  - `_nova-cmo/cmo_agent/core/worker.py`
- CLI
  - `cmo_agent/scripts/cli_run.py` (tqdm, summary/exports)
  - `cmo_agent/scripts/unified_cli.py` (auto mode; imports engine types/events)
- Engine scaffolding
  - `cmo_agent/engine/types.py`
  - `cmo_agent/engine/events.py`
  - `cmo_agent/engine/__init__.py`
- Requirements
  - `cmo_agent/requirements.txt`
  - `_nova-cmo/cmo_agent/requirements.txt`

## Roadmap checkpoints

- Implement `cmo_agent/engine/core.py` with:
  - `create_unified_engine()`
  - `run_inproc(spec, sinks)`
  - `create_cli_sinks(no_emoji=False)` returning a CLI renderer and summary collector
- Move shared summary generation into a dedicated module used by both CLI and worker

---

Questions or gaps? Open a quick issue with the job id and attach the generated files from `./exports/` so we can reproduce quickly.
