## Make-based testing guide (CMO Agent pipeline)

### Why this exists

Use these small, focused make targets to run just one slice of the pipeline at a time. This helps pinpoint where things break (discovery, extraction, enrichment, email finding, export/done, or the execution engine/SSE path).

### TL;DR – One button diagnosis

```bash
make doctor
```

If something fails, re-run the focused slice, e.g.:

```bash
make diag.github
make dry-run GOAL="Find maintainers of Python repos stars:1000..3000 pushed:>=2025-06-01; prioritize active 90 days; export CSV."
make -C cmo_agent start-workers
make smoke-real GOAL="Find maintainers of Python repos stars:1000..3000 pushed:>=2025-06-01; prioritize active 90 days; export CSV."
```

### Prerequisites

- Export credentials before running (at least `GITHUB_TOKEN`).

```bash
export GITHUB_TOKEN=your_token
```

### Quick sanity checks

- **Toolbelt smoke test (local tool calls only)**

```bash
make smoke-tools                 # from repo root
make -C cmo_agent smoke-tools    # directly via cmo_agent Makefile
```

- **Tool availability / env check**

```bash
make -C cmo_agent check-tools
```

### Run a single job (no workers) – fastest repro

- Dry-run, no sending (recommended first):

```bash
make dry-run GOAL="Find maintainers of Python repos stars:1000..3000 pushed:>=2025-06-01; prioritize active 90 days; export CSV."
```

- With a specific config (e.g., smoke settings):

```bash
make run-config \
  CONFIG=cmo_agent/config/smoke.yaml \
  GOAL="Find maintainers of Python repos stars:1000..3000 pushed:>=2025-06-01; prioritize active 90 days; export CSV."
```

### Execution engine path (queue + workers) – tests streaming/completion

1. Start workers (leave running in a terminal):

```bash
make -C cmo_agent start-workers
```

2. Submit a job (new terminal):

```bash
make -C cmo_agent submit-job \
  GOAL="Find maintainers of Python repos stars:1000..3000 pushed:>=2025-06-01; prioritize active 90 days; export CSV."
```

3. Inspect jobs and status:

```bash
make -C cmo_agent list-jobs
make -C cmo_agent job-status JOB_ID=<paste_id_from_list>
```

4. One-shot submit + process (no separate worker step):

```bash
make -C cmo_agent run-job \
  GOAL="Find maintainers of Python repos stars:1000..3000 pushed:>=2025-06-01; prioritize active 90 days; export CSV."
```

### Focused slices you can run repeatedly

- Small demo campaign (dry-run):

```bash
make -C cmo_agent test-campaign
```

- Toolbelt smoke tests (covers GitHub, hygiene, export, done):

```bash
make smoke-tools
```

### When you suspect email discovery is the issue

- Re-run a dry-run with the same goal to isolate just the GitHub tools path. The code uses UTC cutoff, paginated commit scans, author+committer fallback, and emits richer stats for why emails are 0 (e.g., noreply-only). Use the Execution Engine flow above to observe SSE progress and confirm a terminal event is emitted.

### Lead Intelligence (separate pipeline)

```bash
make intelligence-quick     # quick scan (10 repos, 30 days)
make intelligence-test      # unit tests for intelligence pipeline
```

### Cleanup between runs

```bash
make -C cmo_agent clean
make clean
```

### Troubleshooting tips

- If a job appears to “finish without a result,” verify a terminal state was emitted:
  - In the engine path, use `list-jobs` and `job-status` to confirm `completed` or `failed`.
  - Ensure the `done` step was called (final stage should be `completed`).
  - For zero emails: check per-user stats (noreply skipped, pages scanned, author/committer hits).
