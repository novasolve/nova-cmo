# RunState

The **RunState** is the persistent execution context of the CMO Agent.
It ensures that long-running outbound campaigns can be paused, resumed, monitored, and debugged without losing progress.

---

## 📌 Purpose

* Acts as the **single source of truth** during execution.
* Stores all data flowing through the pipeline: discovery results, enriched leads, campaign actions, errors, and metrics.
* Enables **resumability**: crash recovery, pause/resume, and checkpointing.
* Supports **observability**: counters, reports, structured logs, and error context.

---

## 🏗️ Schema

```python
class RunState(TypedDict):
    # Job metadata
    job_id: str             # Unique identifier for this run
    goal: str               # Natural language goal / query

    # Discovery
    repos: List[Dict]       # GitHub repositories discovered
    candidates: List[Dict]  # Initial contributors / maintainers

    # Enrichment
    leads: List[Dict]       # Fully enriched lead profiles

    # Campaign
    to_send: List[Dict]     # Final email payloads queued for dispatch
    reports: Dict           # Aggregate reporting + analytics

    # Monitoring
    counters: Dict          # API call usage, throughput, etc.
    errors: List[Dict]      # Structured error objects with context
```

---

## 🔄 Lifecycle

1. **Initialization**

   * State created with `job_id`, `goal`, and empty collections.
2. **Population**

   * Tools append results (repos → candidates → leads → to\_send).
3. **Execution**

   * Sending & syncing tools consume `to_send`, updating counters and reports.
4. **Checkpointing**

   * State serialized after each major step for durability.
5. **Resumption**

   * On restart, agent re-hydrates state and continues from last checkpoint.
6. **Completion**

   * Final reports + logs are written; `done` signal updates the job record.

---

## ⚡ Persistence & Storage

* Default: In-memory with periodic dumps to `/data/runstate_{job_id}.json`
* Production: Configurable backend (SQLite/Postgres/Redis)
* Each checkpoint is append-only, enabling replay & audit trails.

---

## 📊 Monitoring

* **Counters:**
  Track API usage, throughput, and rate limits.
* **Reports:**
  Store campaign outcomes (delivered, bounced, replied, etc).
* **Errors:**
  Captured with stack trace + input context for replay/debug.

---

## 🛠️ Developer Notes

* Always update `RunState` **immutably** → clone, patch, then re-assign.
* When writing new tools:

  * Accept `state` as input.
  * Return an updated copy.
  * Do not mutate shared state in-place.
* Add schema fields only via PR + schema migration notes.

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

* **Reliability:** Resilient to API errors and crashes.
* **Transparency:** Complete audit log of campaign execution.
* **Extensibility:** Schema designed to grow with new tools and features.

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