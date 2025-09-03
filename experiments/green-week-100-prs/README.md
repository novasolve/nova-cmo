# Green Week — 100 PRs Rescued in 7 Days

Goal: In 14 days, publicly turn 100 failing pull requests green using ≤40‑LOC patches, sharing daily proof and culminating in a Show HN launch. Success KPI: reach $1K MRR from demos, trials, and installs during this period.

Structure:

- `plan.md`: Full project plan, workstreams, milestones, metrics
- `metrics/`: CSVs and docs for daily tracking
- `workstreams/`:
  - `rescue-agent/`: Code skeleton for PR scanning and patching
  - `growth-agent/`: Posting templates and process
  - `dashboard/`: Product brief for live public dashboard
  - `conversion/`: Landing, trial, referral plan

Quickstart (Rescue Agent skeleton):

1. Python 3.10+
2. `cd workstreams/rescue-agent && pip install -r requirements.txt`
3. Set `GITHUB_TOKEN` env var (PAT with repo/read:org status permissions)
4. `python scripts/scan_and_rescue.py --query "is:pr is:open label:ci-failing" --max-prs 5`

Notes:

- Patches must remain ≤40 lines of diff; the runner enforces this limit.
- The initial code is a minimal scaffold to iterate quickly.
