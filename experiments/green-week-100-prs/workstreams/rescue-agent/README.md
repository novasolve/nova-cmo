# Rescue Agent — PR Scanner & Patch Generator

Purpose: Scan GitHub for open PRs with failing CI, generate a ≤40‑LOC patch, and post it respectfully. Supports iterative attempts with re‑runs.

Milestones:

- Day 1: basic agent fixes a simple failing test
- Day 2: 2–3 iteration loop per PR

Run locally:

1. Python 3.10+
2. `pip install -r requirements.txt`
3. Set `GITHUB_TOKEN` (repo/read:org, PR, statuses)
4. `python scripts/scan_and_rescue.py --query "is:pr is:open" --max-prs 5`

Notes:

- Enforces ≤40 lines of diff per attempt
- Posts comments with context; can open a new PR referencing the failing one
- Respect rate limits and project etiquette
