## 🎛️ CMO Agent — UX Flows & Product Behaviors

A practical guide to the end‑to‑end user experience for the single‑agent, tool‑calling LangGraph that powers outbound & CRM operations.

This document translates the active implementation into task‑first UX flows, screens, states, and acceptance criteria. It is framework‑agnostic (works for web app or CLI+TUI) and maps directly to the system’s RunState, tools, and pipeline stages.

For architecture & APIs, see the main repo’s docs referenced below.

This doc focuses on how users experience the system and how we surface the state of a campaign at each step.

### 🔗 Related Docs

- **Complete Specification (Main README)**: [Root README](../README.md)
- **CMO Agent Overview**: [cmo_agent/README](./README.md)
- **Execution Model**: [execution_model_README](./execution_model_README.md)
- **API Reference (Tools)**: [tools/README](./tools/README.md)
- **Single‑Node LangGraph**: [agents/README_SINGLE_NODE_LANGGRAPH](./agents/README_SINGLE_NODE_LANGGRAPH.md)
- **Personalization Payload Spec**: [tools/PERSONALIZATION_PAYLOAD](./tools/PERSONALIZATION_PAYLOAD.md)

### 1) Product Scope & Personas

**Primary personas**

- **Growth Marketer / SDR** — Runs campaigns, reviews leads, approves personalized copy, monitors replies.
- **Revenue/Ops Admin** — Owns credentials, rate limits, CRM mappings, governance (suppression lists, dedupe).
- **Engineer / Builder** — Observability, debugging, failure recovery.

**Top outcomes**

- **Launch a campaign** from an ICP + goal in minutes (optional Dry Run).
- **See a clean, reviewable funnel** from discovery → enrichment → hygiene → personalization → sending → CRM sync → tracking.
- **Pause / resume safely**, fix errors fast, and understand “why” (explanations per lead & per decision).
- **Close the loop**: signals and replies route to CRM + Issues (Linear) with traceable context.

### 2) Navigation & Information Architecture

**Left nav**

- **Dashboard** (active runs, health, alerts)
- **Campaigns** (list + create)
- **Leads** (global lead inbox, search, filters, suppression)
- **Sequences** (Instantly mapping & pacing)
- **CRM Sync** (mappings, dedupe, rules)
- **Issues** (Linear tickets from failures / follow‑ups)
- **Settings** (API keys, rate limits, defaults, roles)

**Entity types**

- **Campaign** — all state for a run (maps 1:1 to RunState).
- **Lead** — person/company with enrichment, hygiene, personalization, send status, CRM status.
- **Sequence** — send program & pacing for Instantly.
- **Issue** — created for errors / follow‑ups.

### 3) Canonical Flow (Happy Path)

#### 3.1 Create a Campaign (Wizard)

**Goal**: Start from a human goal string or preset ICP; validate capacity and show clear expected outcomes.

**Steps**

- **Goal & ICP**
  - Inputs: goal text (freeform), pick ICP preset (languages, topics, stars), optional repo filters.
  - Output preview: expected repo count → contributor count → leads.
- **Limits & Pacing**
  - max_steps, max_repos, max_people, instantly_per_second, daily caps.
  - Show limit warnings (GitHub / Instantly quotas) and calculated ETA as ranges.
- **Personalization**
  - Choose template strategy (from PERSONALIZATION_PAYLOAD), fallback rules, A/B variant (optional).
  - Preview variables the agent expects and which tools produce them.
- **CRM & Sync**
  - Upsert rules (match by email > domain+name), account ownership, status mapping, field mapping.
  - Dedupe policy and suppression lists.
- **Notifications & Governance**
  - Slack/email alerts, dry run toggle, data retention window, export permissions.
- **Review & Launch**
  - Summary card: inputs, constraints, risk checks, projected throughput.
  - Actions: Launch, Dry Run, Save Draft.

**Acceptance Criteria**

- Form validates required creds (GitHub, Instantly, Attio, Linear).
- Capacity prechecks (rate limits, quotas) surface as blocking or soft warnings.
- Dry Run renders a simulated counts + sample previews (no network sends).

#### 3.2 Discovery → Enrichment → Hygiene (Triage Board)

**Goal**: Review and triage before sending.

**UI Model**: 3 columns with stage counters and in‑place filters.

- **Discovery (repos & contributors)**
  - Cards: repo name, stars, topics, top contributors.
  - Actions: Include/Exclude Repo, adjust filters (languages, topics).
- **Enrichment (leads)**
  - Cards: name, GitHub profile, activity, inferred role, company/domain.
  - Actions: Include/Exclude Lead, open lead drawer (full context).
- **Hygiene (deliverability)**
  - Cards: MX check result, bounce risk, role-address warnings (e.g., info@), duplicates found.
  - Actions: Fix / Suppress / Override.

**Acceptance Criteria**

- Stage counters reconcile with RunState.counters.
- Triage decisions persist and are explainable in lead drawer (“Why included/excluded?”).
- Duplicate & suppression checks are visible before personalization.

#### 3.3 Personalization Review

**Goal**: High‑signal copy with minimal manual edits.

**UI Model**: Side‑by‑side preview

- Left: Lead context (repo contributions, recent activity, notable commits/issues).
- Right: Generated email with variable highlights & fallbacks.

**Batch actions**

- Approve all passing thresholds.
- Bulk edit a token (e.g., {recent_contribution}) across selection.
- Flag “Needs Work” to push back to agent with reason (insufficient context, off‑tone, etc.).

**Acceptance Criteria**

- Every personalization shows source snippets (provenance) and confidence scores.
- Fallbacks render deterministically if fields are missing.
- Manual edits are tracked per lead for auditability.

#### 3.4 Sending & Pacing

**Goal**: Queue and send with guardrails.

**UI Model**: Queue Timeline

- Cards show status: QUEUED → SENT → BOUNCED/DELIVERED → REPLIED.
- Visual pacing bars vs. configured rate limits.

**Controls**

- Pause / Resume campaign.
- Adjust caps (per hour/day) without redeploy.
- Retry failed sends with reason.

**Acceptance Criteria**

- Conflicts (same recipient appearing in multiple campaigns) trigger a stop‑ship prompt with resolution options.
- Pacing honors Instantly limits and shows backoff behavior when hit.

#### 3.5 CRM Sync & Issues

**Goal**: Reliable upsert to CRM with transparent matching.

**UI Model:**

- Sync Log — row per lead: match key, operation (create/update/skip), mapped fields.
- Issues (Linear) — created from errors & follow‑ups with deep links back to lead/campaign context.

**Acceptance Criteria**

- Dedupe rationale visible (“Skipped: existing contact with stronger last‑touch in Campaign X”).
- One‑click Re‑sync after field mapping changes.
- Issue tickets include correlation IDs and last failing payload.

#### 3.6 Tracking, Replies & Triage

**Goal**: Route signals and triage replies fast.

**UI Model:**

- Signals: opens, clicks, bounces charts; per‑campaign and per‑sequence views.
- Replies Inbox: sentiment tags (Positive / Neutral / Not Now / Unsubscribe), suggested next action.
- One‑click outcomes: Create Opportunity, Schedule Follow‑up, Mark as Disqualified.

**Acceptance Criteria**

- Reply triage writes structured outcomes to CRM and updates campaign metrics.
- Unsubscribe updates global suppression.

### 4) System States & Transitions

**Campaign status state machine**

```
DRAFT
  → DRY_RUN (optional)
  → DISCOVERING
  → ENRICHING
  → HYGIENE
  → PERSONALIZING
  → QUEUED
  → SENDING
  → SYNCING
  → MONITORING
  → DONE

Any → PAUSED
Any → ERROR (recoverable)
```

Each state maps to RunState slices:

`repos`, `candidates`, `leads`, `to_send`, `reports`, `counters`, `errors`.

**Rule**: Transitions require counters to be internally consistent (e.g., `to_send.length ≤ leads.length`).

### 5) Lead Drawer (Single Source of Truth)

Openable from any list. Shows:

- **Identity**: name, email(s), GitHub, company, role.
- **Evidence**: repos, contributions, recent PRs/issues (links).
- **Hygiene**: MX, bounce risk, dedupe hits.
- **Personalization**: tokens, render output, editable notes.
- **Send & CRM**: sequence assigned, last send result, CRM object link.
- **History**: timeline of agent decisions & manual overrides.

**Acceptance Criteria**

- Every included lead has at least one evidence snippet or an explicit reason for inclusion.
- All decisions are explainable and timestamped.

### 6) Empty States, Errors & Recovery

**Empty States**

- Discovery returns 0: show actionable suggestions (widen stars/topics, adjust languages, add synonyms).
- No valid emails: prompt to enable alternate discovery (e.g., commit emails) with risk notice.

**Common Errors & UX Behaviors**

- Rate limits (GitHub/Instantly): visible backoff with next resume time; campaign auto‑pauses if persistent.
- Credential failure: block progress with clear fix path (Settings deep link).
- CRM mapping mismatch: mark affected leads; allow bulk re‑map & re‑sync.
- MX failure: auto‑suppress or allow override with policy confirmation.

### 7) Governance & Permissions

**Roles**

- **Admin**: credentials, rate limits, field mapping, export permissions.
- **Editor**: create/launch campaigns, approve copy, manage issues.
- **Viewer**: read‑only dashboards & leads.

**Data & Compliance**

- PII minimization in logs, redacted emails by default (toggle for Admin).
- CAN‑SPAM/GDPR notes in first‑run: legal footer, unsubscribe handling, data retention policy.
- Export gated by role + justification note.

### 8) Observability in the UI

- **Health Bar** on all screens: Errors (count), Retries, Paused state, Current throughput.
- **Structured Logs**: filter by lead, tool, correlation ID.
- **Explain pill**: show tool call summary and last payload (redacted as needed).

### 9) Analytics & Event Spec (MVP)

Emit product analytics as structured events (names are stable, props are additive). Examples:

```json
{
  "event": "campaign_created",
  "props": {
    "campaign_id": "cmp_123",
    "goal": "Find 2k Py maintainers active 90d, queue Instantly seq=123",
    "icp": {
      "languages": ["python"],
      "topics": ["ci", "testing", "pytest"],
      "stars_range": "100..2000"
    },
    "limits": { "max_steps": 40, "max_repos": 600, "max_people": 3000 },
    "dry_run": false
  }
}
```

```json
{
  "event": "lead_personalization_reviewed",
  "props": {
    "campaign_id": "cmp_123",
    "lead_id": "lead_456",
    "approved": true,
    "manual_edits": 1,
    "confidence": 0.83
  }
}
```

```json
{
  "event": "crm_upsert_result",
  "props": {
    "campaign_id": "cmp_123",
    "lead_id": "lead_456",
    "operation": "update",
    "match_key": "email",
    "result": "success"
  }
}
```

**Dashboards suggested**

- **Funnel** (Repos → Contributors → Leads → Sendable → Sent → Replied).
- **Deliverability** (MX pass rate, bounce rate).
- **Personalization quality** (avg. confidence, manual edit rate).
- **Sync reliability** (errors over time; time‑to‑fix).

### 10) Microcopy & Tone Guidelines

- **Actionable, specific, and reversible.**
  - “Pause sending” (primary). “Adjust pacing” (secondary).
- **Show why**: always include a short “Because…” reason for blocks or suppressions.
- **Preview before commit**: especially for bulk actions (approve all, retry all).
- **Consistency**: Use the same labels as tool names where helpful (e.g., “MX check”).

### 11) Accessibility & Performance

- Keyboard‑first controls for triage lists and personalization approval.
- Live regions for status changes (Queued → Sent).
- Avoid big blocking spinners: use skeletons with per‑stage counters.
- Time zone: display absolute timestamps (ISO) with friendly local hover.

### 12) Export & Reproducibility

- Export CSV from any stage (respect role).
- Include campaign hash: {config, ICP, template version} to make exports reproducible.
- Download artifacts: copy renders, failure logs (redacted), dedupe decisions.

### 13) Service Blueprint (Front‑Stage ⇄ Back‑Stage)

```
User Action          UI Surface           Agent/Tool Calls                          State Updated
---------------------------------------------------------------------------------------------------------------
Create campaign      Wizard               N/A (validation only)                     Draft config
Launch / Dry Run     Review screen        search_github_repos → extract_people      repos, candidates, counters
Triage repos/leads   Board + drawer       enrich_github_user, find_commit_emails    leads
Hygiene decisions    Hygiene column       mx_check, score_icp                        leads (flags), to_send
Approve copy         Personalization      render_copy                                to_send (approved)
Start sending        Queue timeline       send_instantly (pacing)                    reports
CRM sync             Sync log             sync_attio                                  CRM states, reports
Handle failures      Issues view          sync_linear (issue), retries               errors, counters
```

### 14) MVP → V1 Roadmap (UX)

**MVP**

- Campaign wizard, triage board, personalization preview, queue timeline, basic sync log, issues creation, pause/resume.

**V1**

- Reply triage inbox, A/B personalization, conflict detection across campaigns, global suppression management UI, export with campaign hash, explainability pills, role‑based redaction.

### 15) Glossary

- **ICP**: Ideal Customer Profile.
- **MX Check**: DNS‑based email deliverability validation.
- **Instantly**: Email sending platform used for sequences.
- **Attio**: CRM used for contact/account sync.
- **Linear**: Issue tracker for errors & follow‑ups.
- **RunState**: Persistent, typed state for a campaign execution.
- **Dry Run**: Simulated pipeline with no external sends.

### 16) Acceptance Checklists (Per Flow)

**Create Campaign**

- All credentials verified or clear blocking error.
- Projected counts visible and align with ICP.
- Risk checks shown; Dry Run available.

**Triage & Hygiene**

- Filters + include/exclude persist and are explainable.
- Dedupe + suppression visible pre‑send.
- Hygiene warnings actionable (suppress/override).

**Personalization**

- Source evidence links present for every variable.
- Batch approve / revert works and is traceable.
- Fallbacks render deterministically.

**Send & Sync**

- Pacing obeys caps; conflicts caught.
- CRM upsert rationale and result visible per lead.
- Issues have correlation IDs and retry paths.

**Tracking & Replies**

- Reply outcomes update CRM.
- Unsubscribes update suppression lists globally.

### 17) Example Screen Skeletons (ASCII)

**Campaign Card**

```
┌────────────────────────────────────────────────────────┐
│ Campaign: Py Maintainers 90d   Status: PERSONALIZING   │
│ Repos: 412  Candidates: 2,106  Leads: 1,284  To Send: 870
│ Errors: 3 (View)   Paused: No   Pacing: 7/min (cap 10) │
│ Actions: Resume | Pause | Open                          │
└────────────────────────────────────────────────────────┘
```

**Lead Drawer**

```
Name / Email     GitHub / Company
Evidence         Recent PRs, commits, topics, activity
Hygiene          MX: PASS   Dupes: 1 (view)  Suppressed: No
Personalization  [Rendered email]  [Variables + fallbacks]
Send & CRM       Sequence #123     Last: QUEUED   CRM: Updated
History          [Timeline of decisions + edits]
```

### 18) Implementation Notes (Bridging UX ↔ Code)

- Every list view reads from the canonical RunState slices to avoid drift.
- Use stable IDs (job_id, lead_id) for deep links and correlation.
- Tool calls should surface short human summaries for explainability panes (no raw secrets).
- Errors stored in `RunState.errors[]` must include: tool, payload_hash, human_readable, severity, retryable.

### 19) Out of Scope (for now)

- Multi‑tenant seat management & billing.
- Visual cadence editor for sequences.
- In‑app inbox for all mailboxes (we only show reply triage outcomes initially).

That’s it. With this UX flows README, design can prototype screens, engineering can wire the state and events, and PMs can validate acceptance criteria against the working LangGraph pipeline.
