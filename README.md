# CMO Agent — A Single‑Agent, Tool‑Calling LangGraph for Outbound & CRM Ops (v0.1)

**Owner:** Sebastian (NovaSolve)
**Inspo:** DeepAgents (asynchronous, long‑running plans), Open‑SWE (agentic dev flows)
**Goal:** Chat with a single "CMO" agent (GPT‑5) that can **discover → enrich → personalize → send → sync → track** using a strict toolbelt (GitHub, Instantly/Smartlead, Attio, Linear). Start simple; enable long‑running, resumable jobs.

---

## 1) Objectives & Non‑Goals

### Objectives (MVP)

1. **Chat UX**: natural language → concrete campaign runs.
2. **Single LangGraph node** running a **tool‑calling supervisor** (Planner+Executor) with a typed, persistent **RunState**.
3. **Toolbelt** for: GitHub discovery/enrichment, MX checks, copy rendering, send (Instantly), CRM sync (Attio), ticketing (Linear), export.
4. **Asynchronous execution**: model issues a plan, then works for hours via background workers; progress is streamed to chat and stored in run logs.
5. **Deterministic rails**: step budgets, per‑tool caps, rate‑limit policies, idempotent writes.

### Non‑Goals (for MVP)

- Multi‑agent debate/critique trees.
- Auto‑A/B bandits, reply classification, or calendaring threads.
- Third‑party enrichers (Clay/Apollo) beyond commit/profile emails.

---

## 2) System Overview

```
┌──────── Chat UI ───────┐    enqueue        ┌──────── Runner(s) ─────────┐
│  "Find 2k Py devs"     │ ───────────────▶  │  LangGraph: single node    │
│  "Queue Instantly"     │   job:create      │  GPT‑5 tool‑calling agent  │
└────────────────────────┘                   │  • executes tools w/ caps  │
                                             │  • persists RunState       │
                                             └───────────┬────────────────┘
                                                         │
                                              writes/reads│
                                                         ▼
                                          ┌──────────── State Store ───────────┐
                                          │ run_state, traces, artifacts, CSV  │
                                          └─────────────────────────────────────┘
```

- **Frontend**: your chat with the agent. Commands become **Jobs**.
- **Scheduler/Queue**: enqueues jobs; workers pull and run steps; supports backoff/resume.
- **Runner**: the LangGraph workflow. One node that repeatedly prompts GPT‑5 to choose a **tool** (or `done`).
- **State Store**: SQLite/Postgres + S3‑style blob for artifacts; Langfuse for traces (optional).

---

## 3) Execution Model (Async‑first)

- **Job** = {goal, constraints, env, created_by}. Example: "Find 2000 Py maintainers active 90d, MX‑check, queue Instantly seq=123, sync Attio list=abc; export CSV."
- **Worker loop** pulls job → invokes LangGraph **step** → executes the selected **tool** → **reduces** result into `RunState` → persists → repeats until `done` or **step budget** reached.
- **Streaming progress**: tail structured logs to chat; key milestones push notifications.
- **Pause/Resume**: at any time; all tool calls are idempotent or guarded with external ids.

---

## 4) RunState (typed)

```python
class RunState(TypedDict, total=False):
  job_id: str
  goal: str
  icp: dict                     # keywords, languages, stars, activity window
  repos: list[dict]
  candidates: list[dict]        # {login, from_repo, signal}
  leads: list[dict]             # enriched + scored
  to_send: list[dict]           # {email, subject, body, meta}
  reports: dict                 # instantly/attio/linear/export
  errors: list[dict]            # {stage, payload, error}
  counters: dict                # {steps, api_calls, tokens}
  checkpoints: list[str]        # artifact ids / CSV paths
  config: dict                  # caps, pacing, retries
  ended: bool
```

**Caps (defaults):** `max_steps=40`, `max_repos=600`, `max_people=3000`, `max_tool_calls_per_kind` map.

---

## 5) Toolbelt (contracts)

> All tools must be **pure JSON in/out**, **idempotent**, and enforce their **own rate limiting**.

### GitHub discovery & enrichment

- `search_github_repos(q: str, max_repos: int) -> [Repo]`
- `extract_people(repos: [Repo], top_authors_per_repo: int=5) -> [PersonRef]`
- `enrich_github_user(login: str) -> PersonProfile`
- `find_commit_emails(login: str, repos: [Repo], days: int=90) -> [Email]`

### Hygiene & scoring

- `mx_check(emails: [str]) -> [GoodEmail]`
- `score_icp(profile: PersonProfile, weights: dict) -> Score`
  _Deterministic; expose each feature's contribution._

### Personalization & sending

- `render_copy(lead: Lead, campaign: dict) -> {subject, body}`
  _(Jinja v1; LLM v2; store prompt & output)_
- `send_instantly(contacts: [dict], seq_id: str, per_inbox_cap: int=50) -> SendReport`

### CRM & ticketing

- `sync_attio(people: [dict], list_id: str) -> AttioReport`
  _Upsert People → add to List → Note("Cold email scheduled")_
- `sync_linear(parent_title: str, events: [dict]) -> LinearReport`
  _Create parent campaign; child issues for errors/hot‑replies_

### Export & finalize

- `export_csv(rows: [dict], path: str) -> {path, count}`
- `done(summary: str) -> null`

---

## 6) Single‑Node LangGraph

- **System prompt** anchors the order of operations, caps, and fallback logic.
- The agent **must** use tools; free‑text answers are discouraged.
- A **reducer** maps each tool's result into `RunState`.

**Pseudocode skeleton**

```python
SYSTEM = f"""
You are a CMO operator. Always use TOOLS; do not fabricate.
Order: search→extract→enrich→emails→mx→score→render→send→sync→export→done.
Respect limits: MAX_STEPS={{max_steps}} MAX_REPOS={{max_repos}} MAX_PEOPLE={{max_people}}.
If MX‑passed volume < target, expand query incrementally (lower stars, widen topics) up to caps.
Stop by calling tool: done(summary).
"""

agent = ChatOpenAI(model="gpt-5-thinking", temperature=0).bind_tools(TOOLS)

def agent_step(state: dict):
  msg = prompt.format_messages(input=state["goal"], history=state.get("history", []))
  resp = agent.invoke(msg)
  state.setdefault("history", []).append(resp)
  for call in resp.tool_calls:
    result = TOOL_MAP[call.name](**call.args)
    state = reduce(state, call.name, result)
    if call.name == "done":
      state["ended"] = True
  state["counters"]["steps"] = state.get("counters", {}).get("steps", 0) + 1
  return state
```

---

## 7) Personalization Payload (schema)

```json
{
  "login": "octocat",
  "name": "Monalisa Octocat",
  "best_email": "mo@github.com",
  "signals": {
    "maintainer_of": ["owner/repo1"],
    "recent_pr_titles": ["Fix flaky pytest"],
    "topics": ["pytest", "ci", "devtools"],
    "primary_language": "Python",
    "activity_90d_commits": 23,
    "followers": 512
  },
  "snippets": {
    "why_now": "3 green releases in July; added pytest-xdist; CI minutes spiked 24%",
    "hook": "Nova auto-fixes failing Python tests in CI."
  }
}
```

---

## 8) Observability & Persistence

- **Storage**: `runs/{job_id}/state.json`, `artifacts/*.csv`, `logs/*.ndjson`.
- **Langfuse** (optional): trace per tool call; tags: job_id, stage, repo_count.
- **Metrics**: prospects/min, MX pass‑rate, Instantly acceptance, soft/hard bounces (later).
- **Checkpoints**: write CSV every N=200 leads; resume from last checkpoint on restart.

---

## 9) Rate Limits, Retries, Idempotency

- **GitHub**: backoff on `403` with `X-RateLimit-Reset`; support token pool round‑robin.
- **Instantly**: enforce `per_inbox_daily` + pacing; de‑duplicate by `{email, seq_id}`.
- **Attio**: upsert by email; write idempotency key = `job_id:email`.
- **Linear**: single parent per `job_id`; child issues keyed by error hash.
- **Retries**: exponential backoff with jitter; dead‑letter queue for persistent failures.

---

## 10) Config & Secrets

**Env**

```
OPENAI_API_KEY=...
GITHUB_TOKEN=...
INSTANTLY_API_KEY=...
ATTIO_API_KEY=...
LINEAR_API_KEY=...
STATE_DB_URL=postgres://...
BLOB_DIR=/var/lib/cmo/artifacts
```

**Defaults (overridable per job)**

```yaml
max_steps: 40
max_repos: 600
max_people: 3000
per_inbox_daily: 50
activity_days: 90
stars_range: "100..2000"
languages: [python]
include_topics: [ci, testing, pytest, devtools, llm]
```

---

## 11) UX Flows

### A) Chat‑first

- **You:** "Find \~2k Py maintainers active 90d, queue Instantly seq=123; add to Attio list=abc; export CSV."
- **Agent:** Confirms plan (caps + knobs), creates **Job**, starts running. You can type follow‑ups during execution (it reads the same RunState).

### B) CSV‑first (dry run)

- **You:** "Same, but dry‑run and export only."
- **Agent:** Skips send/sync; writes `prospects.csv` + `attio_people.csv`.

### C) Error triage

- **Agent:** On failure spikes, creates Linear child issues and pauses sending; asks if it should resume after N minutes.

---

## 12) MVP Roadmap (2–3 iterations)

**v0.1 (this doc)**

- Single node, toolbelt wrappers, SQLite state, CSV exports, Instantly send, Attio list sync, Linear error tickets, MX check, basic logs.

**v0.2**

- Token pool for GitHub, parallel enrichment (map/reduce inside tool), resumable checkpoints, Langfuse traces, dry‑run toggle.

**v0.3**

- LLM‑assisted copy (few‑shot with personalization payload), reply webhooks → Linear hot‑reply tasks, simple variant testing (A/B) with counters.

---

## 13) Risks & Mitigations

- **Email sparsity**: Commit emails aren't always present → widen repo topics, add PR authors, allow fallback to profile email.
- **Rate limits**: Use token pool + caching; respect ETags.
- **Nondeterministic agent loops**: Hard step caps; DONE tool; snapshot state per step.
- **Deliverability**: Enforce per‑inbox caps; warm senders; MX sanity checks.

---

## 14) Testing Strategy

- **Unit**: tool contracts (GitHub paging, Instantly batch add, Attio upsert paths).
- **Integration**: canned jobs with mock GitHub/Instantly/Attio fixtures; golden CSVs.
- **Soak**: 3‑hour run across 1k repos; assert checkpoints every 200 leads.

---

## 15) Minimal Code Stubs

```python
# tools/github.py
@tool
def search_github_repos(q: str, max_repos: int = 200) -> list[dict]:
    """Return [{full_name, stars, topics, pushed_at}]."""
    ...

@tool
def extract_people(repos: list[dict], top_authors_per_repo: int = 5) -> list[dict]:
    """Return [{login, from_repo, signal}]"""
    ...

@tool
def enrich_github_user(login: str) -> dict: ...
@tool
def find_commit_emails(login: str, repos: list[dict], days: int = 90) -> list[str]: ...
@tool
def mx_check(emails: list[str]) -> list[str]: ...
@tool
def render_copy(lead: dict, campaign: dict) -> dict: ...
@tool
def send_instantly(contacts: list[dict], seq_id: str, per_inbox_cap: int = 50) -> dict: ...
@tool
def sync_attio(people: list[dict], list_id: str) -> dict: ...
@tool
def sync_linear(parent_title: str, events: list[dict]) -> dict: ...
@tool
def export_csv(rows: list[dict], path: str) -> dict: ...
@tool
def done(summary: str) -> None: return None
```

---

## 16) Open Questions

1. Preferred persistence: SQLite + local blobs vs. Postgres + S3 for immediate scale?
2. Instantly vs. Smartlead default? (Keep both tools behind a flag?)
3. Do we want reply‑classification now or after v0.2?

---

**Verdict:** Ship the single‑agent + toolbelt now. You'll get the "talk to your CMO" UX with guardrails, and a spine that scales to hours‑long runs without wrecking determinism.
