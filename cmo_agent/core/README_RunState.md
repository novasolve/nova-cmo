This document is written for internal developers working on the CMO Agent execution engine.

# RunState — Single Source of Truth for Job Execution

## TL;DR
RunState is the durable, JSON-serializable snapshot of a job. The LangGraph agent reads RunState, tools produce results, and a reducer merges those results back into RunState. We checkpoint it frequently so jobs can pause, resume, and recover without losing progress.

## Table of Contents

- Why RunState exists
- Lifecycle & where it’s used
- Schema (fields & invariants)
- Reducer rules (how tools write to state)
- Serialization & persistence
- Size, safety & performance
- Extending the schema
- Examples (snapshots)
- Integration points
- Testing checklist

## Why RunState exists

Long-running campaigns can span hundreds of tool calls and hours of runtime. RunState enables:

- Deterministic progress: one place to read/write the job’s evolving state.
- Idempotency: tools write structured results; reducers merge safely.
- Resumability: persist to disk/DB; reload after crashes or pauses.
- Observability: counters, reports, and error history.

---

## 🏗️ Schema

```python
from typing import TypedDict, List, Dict, Any

class RunState(TypedDict, total=False):
    # Job metadata (immutable per job)
    job_id: str
    goal: str
    created_at: str
    created_by: str

    # Versioning & control
    state_version: int              # schema version for migrations
    current_stage: str              # e.g. "discovery", "enrichment", ...
    ended: bool                     # termination signal for the graph

    # ICP filters
    icp: Dict[str, Any]             # languages, stars_range, activity_days, topics

    # Pipeline data
    repos: List[Dict[str, Any]]
    candidates: List[Dict[str, Any]]
    leads: List[Dict[str, Any]]
    to_send: List[Dict[str, Any]]

    # Reporting & monitoring
    reports: Dict[str, Any]
    errors: List[Dict[str, Any]]    # structured ErrorEntry
    counters: Dict[str, Any]        # {steps, api_calls, tokens, tool_calls_by_kind, ...}

    # Checkpoints & config
    checkpoints: List[str]          # artifact paths/ids (CSV, JSON)
    checkpoints_meta: List[Dict[str, Any]]  # {id, created_at, stage, type, reason, path}
    config: Dict[str, Any]          # caps, pacing, retries

    # History & governance
    history: List[Dict[str, Any]]   # conversation/decisions (bounded)
    idempotency_keys: Dict[str, str]
    privacy: Dict[str, Any]         # {redact_pii: bool, pii_fields: [...]}
```

## 🔍 Current vs Target RunState

### What we have today

- Typed `RunState` with optional fields covering:
  - Job metadata: `job_id`, `goal`, `created_at`, `created_by`
  - ICP: `icp` criteria
  - Pipeline data: `repos`, `candidates`, `leads`, `to_send`
  - Reporting/monitoring: `reports`, `counters`, `errors`, `checkpoints`
  - Configuration and control flow: `config`, `ended`, `current_stage`, `history`
- `JobMetadata` helper to generate consistent identifiers and timestamps
- `DEFAULT_CONFIG` including:
  - Limits: `max_steps`, `max_repos`, `max_people`, `per_inbox_daily`, `activity_days`
  - Discovery filters: `stars_range`, `languages`, `include_topics`
  - Rate limits/timeouts/retries (exponential backoff, jitter, caps)
  - Error handling policy with retryable/rate-limit/permanent categories and circuit breaker
  - Standard directories for exports/checkpoints/logs/artifacts
- Robust runtime helpers:
  - `RetryConfig` (backoff/jitter/max backoff/rate-limit retry-after)
  - `ErrorHandler` with circuit breaker and `execute_with_retry`
  - `RateLimitDetector` (HTTP 429, GitHub headers, common phrases)
  - `APIErrorHandler` for API-specific classification (GitHub-aware rate limit)
- Agent integration points for checkpoints and progress extraction (see `cmo_agent/agents/cmo_agent.py`)

### What we should add next

- State versioning and migrations
  - Add `state_version: int`
  - Provide `migrate_run_state(state) -> RunState` for backward compatibility
- Stronger typing for nested structures
  - Define `RepoEntry`, `CandidateEntry`, `LeadEntry`, `EmailPayload`, `ErrorEntry`
  - Improves editor assistance and data validation
- Checkpoint metadata and APIs
  - Track `{id, created_at, stage, reason, type}` per checkpoint
  - Helper: `save_checkpoint(state, type, reason)` and `load_latest_checkpoint(job_id)`
- Progress and idempotency
  - `progress: {stage, step, total_steps, items_processed, items_total}`
  - `idempotency_keys` for send/sync operations to avoid duplicates
- Stage cursors for resumability at scale
  - `cursors: {discovery: {...}, enrichment: {...}, personalization: {...}, sending: {...}}`
  - Example: last repo/index processed, pagination tokens, rate-limit reset times
- Size and PII controls
  - `privacy: {redact_pii: bool, fields: [..]}` and trimming/TTL policies for large lists
- Observability hooks
  - `correlation_id`, `trace_ids`, and per-tool metrics (`duration_ms`, `tokens_used`, `api_calls`)
- Persistence abstraction
  - File-based by default, optional SQLite/Postgres/Redis adapters behind a small interface

### Proposed field additions (illustrative)

```python
class ErrorEntry(TypedDict, total=False):
    stage: str
    tool: str
    payload: Dict[str, Any]
    error: str
    timestamp: str
    retry_count: int
    category: str  # retryable | rate_limit | permanent

class ProgressSnapshot(TypedDict, total=False):
    stage: str
    step: int
    total_steps: int
    items_processed: int
    items_total: int
    started_at: str
    updated_at: str

class CheckpointMeta(TypedDict, total=False):
    id: str
    created_at: str
    stage: str
    reason: str
    type: str  # periodic | error | final

class RunState(TypedDict, total=False):
    # ... existing fields ...
    state_version: int
    progress: ProgressSnapshot
    checkpoints_meta: List[CheckpointMeta]
    idempotency_keys: Dict[str, str]
    cursors: Dict[str, Dict[str, Any]]
    privacy: Dict[str, Any]
```

### Minimal helper APIs to add

```python
def migrate_run_state(state: RunState) -> RunState: ...
def save_checkpoint(job_id: str, state: RunState, *, type: str, reason: str) -> str: ...
def load_latest_checkpoint(job_id: str) -> RunState: ...
def get_progress(state: RunState) -> Dict[str, Any]: ...
def next_cursor(state: RunState, stage: str, **kwargs) -> RunState: ...
```

These additions make the RunState safer to evolve, easier to resume at scale, and more observable in production while keeping the current simple flow intact.

---

## 🔄 Lifecycle

1. **Initialization**

   - State created with `job_id`, `goal`, and empty collections.

2. **Population**

   - Tools append results (repos → candidates → leads → to_send).

3. **Execution**

   - Sending & syncing tools consume `to_send`, updating counters and reports.

4. **Checkpointing**

   - State serialized after each major step for durability.

5. **Resumption**

   - On restart, agent re-hydrates state and continues from last checkpoint.

6. **Completion**

   - Final reports + logs are written; `done` signal updates the job record.

---

## ⚡ Persistence & Storage

- Default: In-memory with periodic dumps to `/data/runstate_{job_id}.json`
- Production: Configurable backend (SQLite/Postgres/Redis)
- Each checkpoint is append-only, enabling replay & audit trails.

---

## 📊 Monitoring

- **Counters:**
  Track API usage, throughput, and rate limits.
- **Reports:**
  Store campaign outcomes (delivered, bounced, replied, etc).
- **Errors:**
  Captured with stack trace + input context for replay/debug.

---

## 🛠️ Developer Notes

- Always update `RunState` **immutably** → clone, patch, then re-assign.
- When writing new tools:

  - Accept `state` as input.
  - Return an updated copy.
  - Do not mutate shared state in-place.

- Add schema fields only via PR + schema migration notes.

---

## 🚀 Example

```python
from cmo_agent.core.state import RunState

state = RunState(job_id="job_123", goal="Find active ML engineers")

# Append discovery results
state["repos"].append({"name": "transformers", "stars": 100000})
state["counters"]["github_api_calls"] += 1

# Add lead
state["leads"].append({"login": "janedoe", "email": "jane@example.com"})

# Queue for sending
state["to_send"].append({
    "recipient": "jane@example.com",
    "subject": "Loved your recent PR on transformers"
})
```

---

## ✅ Key Benefits

- **Reliability:** Resilient to API errors and crashes.
- **Transparency:** Complete audit log of campaign execution.
- **Extensibility:** Schema designed to grow with new tools and features.

---

## 📈 Data Flow Diagram

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Discovery     │───▶│   Enrichment     │───▶│ Personalization │
│   (GitHub)      │    │   (Profiles)     │    │   (Emails)      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ repos: []       │    │ leads: []        │    │ to_send: []     │
│ candidates: []  │    │                  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Execution     │───▶│   Reporting      │───▶│   Monitoring    │
│   (Send/Sync)   │    │   (Analytics)    │    │   (Counters)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ reports: {}     │    │ counters: {}     │    │ errors: []      │
│                 │    │ checkpoints: []  │    │                 │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```
