# Toolbelt

Minimal, practical docs for building, running, and extending tools in CMO Agent.

> Design goal: each tool is safe to retry, easy to observe, and interoperable via a shared data contract in `RunState`.

## What is a “Tool”?

- Reads the `RunState`, performs a side‑effect or computation, and returns an updated `RunState`.
- All tools implement a common interface:

```python
class BaseTool(Protocol):
    name: str
    stage: str  # e.g., "discovery" | "enrichment" | "personalization" | "sending" | "sync" | "utility"
    def execute(self, state: RunState, **kwargs) -> RunState: ...
```

- Tools must be idempotent (safe to retry) and append-only (avoid destructive mutation).

## Cross‑Tool Data Contract (80/20)

These minimal shapes are what other tools can rely on. Add more fields as needed, but do not break these.

```python
# Discovery
RepoEntry = TypedDict("RepoEntry", {
  "full_name": str,          # "org/repo"
  "html_url": str,
  "stars": int,
  "topics": list[str],
  "primary_language": str,
  "pushed_at": str           # ISO8601
}, total=False)

CandidateEntry = TypedDict("CandidateEntry", {
  "login": str,              # GitHub username
  "user_id": int,
  "html_url": str,
  "contributions": int,
  "emails": list[str],
  "last_active_at": str      # ISO8601
}, total=False)

# Enrichment
LeadEntry = TypedDict("LeadEntry", {
  "login": str,
  "name": str,
  "email": str,
  "email_status": str,       # "valid" | "mx_missing" | "unknown"
  "icp_score": int,          # 0..100
  "icp_reason": str
}, total=False)

# Personalization / Sending
EmailPayload = TypedDict("EmailPayload", {
  "recipient": str,          # email
  "subject": str,
  "body_text": str,
  "sequence_id": str,        # Instantly sequence
  "schedule_at": str         # ISO8601 optional
}, total=False)
```

RunState anchors:

- `repos: list[RepoEntry]`
- `candidates: list[CandidateEntry]`
- `leads: list[LeadEntry]`
- `to_send: list[EmailPayload]`

Monitoring & safety:

- `errors: list[ErrorEntry]` where `ErrorEntry.category in {"retryable","rate_limit","permanent"}`
- `counters: dict[str, int]` (per‑tool increments)
- `idempotency_keys: dict[str, str]` (fingerprints of side‑effects)
- `reports: dict[str, Any]` (aggregate campaign results)

## Credentials & Config

Set via environment variables (see project README.md): `GITHUB_TOKEN`, `INSTANTLY_API_KEY`, `ATTIO_API_KEY`, `LINEAR_API_KEY`, `OPENAI_API_KEY`.

Global rate limits (overridable via YAML config):

```yaml
rate_limits:
  github_per_hour: 5000
  instantly_per_second: 10
```

## Calling a Tool (Pattern)

```python
tool = SearchGithubRepos()  # from cmo_agent.tools.github
state = tool.execute(state, q="ci testing", stars_range="100..2000", languages=["python"])
# Always reassign: state = updated_state
```

Invariants:

- No in‑place mutation: clone → change → return.
- Append only: tools append to collections or update known keys.
- Checkpoint at boundaries: agent saves state after each stage.

## Tool Catalog (at a glance)

| Tool                  | Purpose                             | Consumes             | Produces/Mutates            | Side‑Effects | Idempotency Key (suggested)       |
| --------------------- | ----------------------------------- | -------------------- | --------------------------- | ------------ | --------------------------------- |
| `search_github_repos` | Find repos by ICP filters           | `config.default_icp` | `repos += RepoEntry[]`      | No           | N/A                               |
| `extract_people`      | Top contributors/maintainers        | `repos`              | `candidates += Candidate[]` | No           | N/A                               |
| `enrich_github_user`  | Expand candidate profiles           | `candidates`         | `leads += LeadEntry[]`      | No           | N/A                               |
| `find_commit_emails`  | Pull commit‑level emails            | `repos`/`candidates` | `candidates[].emails`       | No           | N/A                               |
| `mx_check`            | Validate deliverability             | `leads[].email`      | `leads[].email_status`      | No           | N/A                               |
| `score_icp`           | Deterministic scoring vs. ICP       | `leads`              | `leads[].icp_score/reason`  | No           | N/A                               |
| `render_copy`         | Personalized email text             | `leads`              | `to_send += EmailPayload[]` | No           | N/A                               |
| `send_instantly`      | Dispatch emails via Instantly       | `to_send[]`          | `reports.sent++`            | Yes          | `job:stage:recipient:payloadhash` |
| `sync_attio`          | Upsert lead + campaign data         | `leads`, `reports`   | `reports.crm_upserts++`     | Yes          | `job:attio:email`                 |
| `sync_linear`         | Create issues for follow‑ups/errors | `errors`, `leads`    | `reports.linear_issues++`   | Yes          | `job:linear:subjecthash`          |
| `export_csv`          | Export runtime data                 | `leads`, `to_send`   | File(s) under `/data/`      | File I/O     | `job:export:kind:timestamp`       |
| `done`                | Mark completion                     | `reports`            | `reports.finished_at`       | No           | N/A                               |

Idempotency rule of thumb: `key = sha1(json.dumps(payload, sort_keys=True))[:12]` and prefix with `job_id` + `stage`.

## Personalization payload docs

See `PERSONALIZATION_PAYLOAD.md` for the schema, field mappings, examples, and extension points.

## Concise Tool Specs

### GitHub Tools

#### `search_github_repos`

- Args: `q: str | None`, `languages: list[str]`, `topics: list[str]`, `stars_range: str ("100..2000")`, `max_repos: int`
- Reads: `config.default_icp`, `counters`
- Writes: `repos += RepoEntry`
- Errors: `rate_limit`, `retryable`, `permanent`
- Counters: `github.api_calls`, `repos.discovered`

#### `extract_people`

- Args: `per_repo: int` (top N), `maintainers_only: bool`
- Reads: `repos`
- Writes: `candidates += CandidateEntry`
- Counters: `candidates.discovered`

#### `enrich_github_user`

- Args: `fields: list[str] = ["profile","company","followers","activity"]`
- Reads: `candidates`
- Writes: `leads += LeadEntry` (merge by `login`)
- Counters: `leads.enriched`

#### `find_commit_emails`

- Args: `since: str (ISO) | None`, `max_commits_per_repo: int`
- Reads: `repos`, `candidates`
- Writes: `candidates[i].emails += [...]`
- Counters: `emails.found`

### Hygiene

#### `mx_check`

- Writes: `leads[i].email_status`
- Counters: `mx.checked`, `mx.valid`

#### `score_icp`

- Writes: `leads[i].icp_score`, `leads[i].icp_reason`
- Counters: `icp.scored`

### Personalization & Sending

#### `render_copy`

- Args: `template: str | None`, `style: str = "concise"`
- Reads: `leads`
- Writes: `to_send += EmailPayload`
- Counters: `copy.rendered`, `tokens.used` (if LLM)

#### `send_instantly`

- Side‑effects: Instantly API send; respects rate limits
- Idempotency: skip if idempotency key seen
- Writes: `reports.sent++`, `reports.bounced++`, `reports.rejected++`
- Counters: `instantly.sent`, `instantly.retries`, `instantly.errors`

### CRM Sync

#### `sync_attio`

- Side‑effects: Attio API upsert
- Idempotency: key on `email`
- Counters: `attio.upserts`, `attio.errors`

#### `sync_linear`

- Side‑effects: Linear issue create
- Idempotency: key on `subject`/`body` hash
- Counters: `linear.created`, `linear.errors`

### Utility

#### `export_csv`

- Args: `what: "leads"|"to_send"|"reports"`, `path: str = "data/exports/*.csv"`
- Writes: CSV files, updates `reports.exports[]`
- Counters: `exports.written`

#### `done`

- Writes: `reports.finished_at = now()`, `reports.summary`
- Counters: `pipeline.completed = 1`

## Retries, Rate Limits & Errors

- Retry policy: exponential backoff + jitter; respect `Retry-After`.
- Error categories: `rate_limit`, `retryable`, `permanent`.
- Tool responsibilities: capture errors to `state["errors"]`, increment counters; compute idempotency key before side‑effects.

## Privacy & PII

- Redact PII in logs/exports if `state["privacy"].get("redact_pii", True)`.

## Testing (80/20)

- Unit tests: mock HTTP; assert no in‑place mutation, idempotency, counters/errors updated, contract fields present.
- Integration tests: run sequence on tiny fixture and diff `RunState`.

## Adding a New Tool (checklist)

- Implement `BaseTool` with `name`, `stage`, `execute`.
- Respect the contract fields and idempotency.
- Update counters and append structured errors.
- Wire it in and add a test.

## Troubleshooting

- Duplicate sends/issues → verify idempotency key computation/storage.
- Rate‑limit stalls → include reset and obey backoff.
- Missing `to_send` → check `email_status == "valid"` and ICP threshold.
- Empty CSV → confirm `what` and collections before export.

## Example end‑to‑end

```python
state = init_state(job_id="demo", goal="Find PyCI folks")

state = SearchGithubRepos().execute(state, languages=["python"], topics=["ci","testing"], stars_range="100..2000")
state = ExtractPeople().execute(state, per_repo=5)
state = EnrichGithubUser().execute(state)
state = FindCommitEmails().execute(state)
state = MxCheck().execute(state)
state = ScoreICP().execute(state)
state = RenderCopy().execute(state, template=None, style="concise")
state = SendInstantly().execute(state)
state = SyncAttio().execute(state)
state = SyncLinear().execute(state)
state = ExportCsv().execute(state, what="leads")
state = Done().execute(state)
```
