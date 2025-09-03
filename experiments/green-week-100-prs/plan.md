# Experiment 2: Green Week – Project Plan to Fix 100 Failing PRs

## Goal

In 14 days, publicly turn 100 failing pull requests green with ≤40‑LOC patches, sharing daily proof (threads, Looms), culminating in a Show HN launch. Success: $1K MRR from demos, trials, and installs within this period.

## Workstream 1: Rescue Agent (Automated PR Patches)

- Build PR Scanner & Patch Generator (Assignee: Engineering Lead, Label: Engineering)
  - Agent scans GitHub for open PRs with failing CI, fetches failures, generates ≤40‑LOC fix, pushes patch, triggers re‑run.
  - Milestone: Basic agent operational by Day 1 (fix simple failing test)
  - Metric: PRs attempted vs. rescued per day (target ~15/day)
- Iterative Fix & Re‑run Loop (Assignee: Backend Eng, Label: Automation)
  - After applying a patch, re‑run CI; if still failing, refine fix with another ≤40‑LOC patch (limited iterations).
  - Milestone: Day 2 handles 2–3 iterations/PR
  - Metric: Average TTR < 24h from first attempt to green CI
- GitHub Integration & Etiquette (Assignee: DevOps Eng, Label: Integration)
  - Use bot account; comment on original PR with proposed fix or open a new PR referencing the failing one; include polite disclosure.
  - Milestone: Mid‑week, all patches posted respectfully
  - Metric: Acceptance rate > 50% (merged by maintainers)
- Quality & Limit Safeguards (Assignee: QA, Label: Engineering)
  - Enforce ≤40 LOC, lint/style checks, human review for borderline changes.
  - Milestone: Zero reverts/complaints
  - Metric: ~0% rollback or negative feedback

## Workstream 2: Growth Agent (Daily Social Proof & Content)

- Daily Progress Threads & Loom Videos (Assignee: Founder, Label: Marketing)
- Community Engagement (Assignee: Founder, Label: Community)
- Content Calendar & Launch Prep (Assignee: Marketing Lead, Label: Launch)
- Teaser & Handoff to Launch

## Workstream 3: Dashboard & Real‑Time Proof Publishing

- Live “Green Week” Dashboard (Assignee: Frontend Eng, Label: Product)
- CI Status Integration (Assignee: Frontend Eng, Label: DevOps)
- Design for Trust (Assignee: Designer, Label: UX)
- Metrics & Monitoring

## Workstream 4: Conversion Funnel (Demos, Trials & Installs)

- Landing Page & Sign‑Up (Assignee: Growth PM, Label: Conversion)
- Demo Scheduling (Assignee: Sales Engineer, Label: Sales)
- Trial Onboarding Optimization (Assignee: Product Eng, Label: Onboarding)
- Referral Incentives (Assignee: Marketing, Label: Growth)
- Metrics Tracking

## Phase 1: Execution Timeline (Days 1–7)

- Day 1: Kickoff, first PR rescued, intro thread, dashboard live
- Days 2–5: ~20 PRs/day; daily updates; iterate agent
- Day 6: 80+ PRs green; finalize launch assets; teaser
- Day 7: Hit 100; recap thread; finalize launch readiness

## Phase 2: Launch Day (Show HN)

- Post at ~9 AM PST; title: “Show HN: An AI fixed 100 failing PRs in a week (≤40 LOC each)”
- All‑day engagement; FAQs; referral code for HN
- Social synergy; success tracking

## Phase 3: Post‑Launch Conversion (Days 9–14)

- Personal follow‑ups; onboarding support; community
- Blog post recap; continued social proof
- Measure & optimize conversion to $1K MRR; post‑mortem & next steps

## Outcome Metrics to Track

- PRs rescued/day; acceptance rate; average TTR (<24h)
- Daily social reach; dashboard traffic
- Launch‑day metrics (HN); conversion to $1K MRR (~10 users at $100/mo)

## Future Enhancements (Post‑Success)

- Predictive PR targeting; auto‑generated Looms from diffs
- AI‑driven referral; self‑learning patch agent
- Expanded AI DevOps assistant (CI coach)
