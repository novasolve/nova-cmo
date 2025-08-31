## 9) Rate Limits, Retries, Idempotency

This document explains how the system protects upstream services and itself using rate limiting, retry/backoff, circuit breaking, and idempotency. It covers both the CMO Agent runtime and the Lead Intelligence collectors.

### Scope

- CMO Agent: tool execution layer, error handling, monitoring, and in‑memory idempotency cache
- Lead Intelligence: GitHub collection with conservative pacing and SQLite‑backed deduplication

---

## How it works

### Rate limiting

- CMO Agent tools enforce a per‑tool minimum call interval via `RateLimiter`.
  - Code: `cmo_agent/tools/base.py` (`RateLimiter`, `BaseTool._execute_with_retry`)
- Central error handling detects rate‑limit signals and instructs callers to back off.
  - Code: `cmo_agent/core/state.py` (`RateLimitDetector`, `APIErrorHandler`)
  - Supports HTTP 429 + `Retry-After`, and GitHub `X-RateLimit-Remaining/Reset` headers
- Lead Intelligence client applies conservative GitHub pacing and sleeps until reset when needed.
  - Code: `lead_intelligence/core/data_collector.py` (`GitHubSearchClient._make_request`, `_wait_for_rate_limit_reset`)

### Retries, backoff, circuit breaker

- Unified retry policy with exponential backoff and optional jitter.
  - Code: `cmo_agent/core/state.py` (`RetryConfig`, `ErrorHandler.execute_with_retry`)
  - Rate‑limit errors use a fixed `rate_limit_retry_after` delay; retryable errors use exponential backoff
- Circuit breaker prevents hot‑looping when repeated failures occur and gradually recovers.
  - Code: `cmo_agent/core/state.py` (`ErrorHandler` with `closed/open/half_open` states)
- Worker loop also backs off between top‑level failures to reduce thrash.
  - Code: `cmo_agent/core/worker.py` (sleep on error in main loop)

### Idempotency

- Toolbelt caches successful tool results by an idempotency key (in‑memory TTL cache).
  - Code: `cmo_agent/tools/toolbelt.py` (`_IdempotencyCache`, `compute_idempotency_key`, `execute`)
  - Default TTL is configurable; only successful results are cached to avoid masking real errors
- Keys are computed from `(tool_name, args)` via a stable hash; callers can override `idempotency_key`.
- Service‑specific guidance (documented in tools README):
  - Instantly (email): de‑duplicate by `{recipient_email, sequence_id}`
  - Attio (CRM): upsert by email; recommended idempotency key `job_id:email`
  - Linear (tickets): one parent per `job_id`; child issues keyed by error hash
  - See: `cmo_agent/tools/README.md` (Idempotency notes per tool)

### Deduplication (Lead Intelligence)

- Separately from idempotency, prospect collection uses database‑backed deduplication across runs.
  - Code: `lead_intelligence/core/data_collector.py` (`Deduper`), `github_prospect_scraper.py` (SQLite table `seen_people`)
  - Can be disabled via CLI flag or custom DB path

---

## Configuration

The following settings are defined in `cmo_agent/config/default.yaml` (also `dev.yaml`). Adjust as needed:

```yaml
# Rate limits
rate_limits:
  github_per_hour: 5000
  instantly_per_second: 10

# Retry configuration
retries:
  max_attempts: 3
  backoff_multiplier: 2.0
  jitter: true
  max_backoff_seconds: 300 # 5 minutes max
  rate_limit_retry_after: 60 # Wait 60s after rate limit

# Error handling configuration
error_handling:
  retryable_errors:
    - ConnectionError
    - TimeoutError
    - httpx.ReadTimeout
    - httpx.PoolTimeout
    - aiohttp.ClientConnectorError
  rate_limit_errors:
    - RateLimitError
    - TooManyRequests
    - GitHubRateLimitError
    - CircuitBreakerOpenError

# Feature flags
features:
  enable_rate_limiting: true
```

Lead Intelligence (GitHub collector) also has defaults for pacing and dedup:

- Config file: `lead_intelligence/config/intelligence.yaml` (see defaults for limits, dedupe DB path)
- CLI flags via `github_prospect_scraper.py` and `run_scraper.sh`:
  - `--no-dedup` to disable deduplication
  - `--dedup-db PATH` to specify a custom SQLite path

---

## Usage examples

### Overriding idempotency key for a tool call

When executing a tool through the Toolbelt, you can pass a stable business key instead of the auto‑computed `(tool,args)` hash:

```python
result = await toolbelt.execute(
    "sync_attio",
    job_id=job.id,
    args={"email": lead.email, "payload": payload},
    idempotency_key=f"{job.id}:{lead.email}",
    timeout_seconds=60,
)
```

### Tuning retry behavior

- Increase `retries.max_attempts` for flaky networks
- Raise `retries.rate_limit_retry_after` for stricter APIs
- Disable jitter by setting `retries.jitter: false` to make delays fully predictable

---

## Monitoring

The agent reports rate‑limit incidents and API call stats:

- Code: `cmo_agent/core/monitoring.py` (`api_rate_limits_hit`, success rate, calls by endpoint)
- Use these metrics to validate pacing and to right‑size the configured limits

---

## Best practices

- Prefer business‑stable idempotency keys at call sites that create external side effects
- Keep rate‑limit buffers conservative; use `enable_rate_limiting: true`
- Treat retries as a mitigation, not a fix—surface persistent failures to Linear/alerts
- Use deduplication for collection pipelines and idempotency for side‑effectful writes

---

## References

- Rate limit detection and handling: `cmo_agent/core/state.py`
- Tool‑level pacing and retries: `cmo_agent/tools/base.py`
- Toolbelt idempotency cache and keys: `cmo_agent/tools/toolbelt.py`
- Monitoring counters: `cmo_agent/core/monitoring.py`
- GitHub client pacing and backoff: `lead_intelligence/core/data_collector.py`
- Prospect deduplication: `github_prospect_scraper.py`, `run_scraper.sh`
