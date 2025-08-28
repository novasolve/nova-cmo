Attio CRM — OSS Maintainers Data Model (Final)

This document consolidates the full Attio object model for OSS maintainers, covering People, Repos, Signals, Repo Membership, Companies, and Deals. It specifies:

Objects & their purpose

Attributes (type, constraints, AI)

Relationships & cardinality

Upsert keys for imports

CSV headers

Views & dashboards

AI autofill & automation settings

0. Naming Conventions

snake_case for importable fields (e.g., repo_full_name).

Human-facing AI fields: sentence case (e.g., Repo Summary).

All upsert keys are unique & required.

1. Core Objects
   1.1 People (Standard)

Represents OSS maintainers / contributors.

Identity & Keys

login • Text • Unique ✅ • Required ✅ — GitHub username (primary upsert)

id • Text — GitHub numeric ID

node_id • Text — GitHub GraphQL node ID

lead_id • Text — Internal hash from scraper

Profile

name • Personal Name

company • Text

bio • Text

location • Location

pronouns • Text

avatar_url • Text/URL

html_url • Text/URL

github_user_url • Text/URL

api_url • Text/URL

Emails

email_profile • Email

email_public_commit • Email

Predicted Email • Text • AI Autofill → Research agent

Stats

public_repos • Number

public_gists • Number

followers • Number

following • Number

Timestamps

created_at • Date

updated_at • Date

AI/Outbound Fields

Personal Bio Summary • Text • AI Autofill → Summarize record

Recommended Icebreaker • Text • AI Autofill → Summarize record

Likely Pain Points • Text • AI Autofill

Relationship Strength • Number (system)

Engagement Score • Number (AI Autofill)

Rollups

repos_maintained_count • Number — count of related Repo Memberships

stars_sum_across_repos • Number — sum of related Repos.stars

last_signal_at • Timestamp — max timestamp of related Signals

Upsert key: login (fallback: id)

1.2 Companies (Standard)

Represents employers or OSS orgs. We primarily link People → Company and optionally aggregate repo metrics by org.

Identity & Core

# Record ID • Text • Unique (Attio system)

Domains • Domain • Unique — canonical web/email domain(s)

Name • Text

Description • Text • AI: Summarize record — one‑liner summary

Social / URLs

Logo URL • Text/URL

Github URL • Text/URL — org or main repo

Website • Text/URL (if present in your workspace)

LinkedIn • Text/URL

Twitter • Text/URL

Facebook • Text/URL

Instagram • Text/URL

AngelList • Text/URL

Firmographics (most of these already exist in your workspace, keep using them)

Industry • Multi‑select • AI Autofill

Business Model • Select (B2B, B2C, OSS, etc.) • AI Autofill

Employee Count • Number

Employee range • Select (1–10, 11–50, …) • AI Autofill

Estimated ARR • Select (bucketed) • AI Autofill

Total Funding Raised • Currency • AI Autofill

Latest Funding Round (Type) • Text • AI Autofill

Latest Funding Amount • Currency • AI Autofill

Latest Funding Date • Text/Date • AI Autofill

Foundation date • Date • AI Autofill

Engagement / CRM (system/enriched fields already present)

Interactions: First/Last/Next calendar interaction, First/Last/Next email interaction • Interaction (system fields)

Connection: Connection strength (level) • Number, Connection strength • Select

Metrics & Rollups (additions we use for OSS)

oss_repos_count • Number — rollup count of related Repos with owner_login matching the company/org

total_stars_across_repos • Number — rollup sum of Repos.stars for the org

maintainers_count • Number — rollup count of People linked to this company with role in {owner, maintainer}

Maintainers • Text • AI: Summarize record — short list of top maintainers and flagship repos

Relationships

Companies ↔ People (standard one‑to‑many)

Companies ↔ Repos (optional many‑to‑many) — link org to its repos via matching owner_login

Companies ↔ Deals (standard one‑to‑many)

Upsert Key

Use Attio’s system # Record ID. For enrichment via imports, prefer Domains as a stable match key.

AI Autofill — guidance to paste

Description / Maintainers: “Summarize the company in 1 sentence and mention any notable OSS repos and maintainers we track. Audience: sales research.”

Industry / Business Model / Employee range / ARR / Funding fields: “Infer from public data on the company website/LinkedIn or existing attributes when missing. Keep outputs succinct.”

1.3 Deals (Standard)

Tracks pipeline opportunities.

Key fields

Deal name • Text • Required ✅

Deal stage • Status • Required ✅

Deal value • Currency

Deal owner • User • Required ✅

Associated People • Relationship

Associated Companies • Relationship

AI Fields

Deal Overview (AI Summary) • Text • AI Autofill → Summarize record

Win/Loss Insights • Text • AI Autofill

Suggested Next Step • Text • AI Autofill

Upsert key: Attio default (system # Record ID)

1.4 Repos (Custom)

Each open-source repo.

Identity

repo_full_name • Text • Unique ✅ • Required ✅ — Record label

repo_name • Text

owner_login • Text

host • Select (GitHub | GitLab | Bitbucket)

Metadata

description • Long text • AI Autofill → Summarize record

topics • Multi-select

primary_language • Text • AI Autofill → Classify record (if missing)

license • Text

Popularity & Hygiene

stars • Number

forks • Number

watchers • Number

open_issues • Number

is_fork • Checkbox

is_archived • Checkbox

Timestamps

created_at • Timestamp

updated_at • Timestamp

pushed_at • Timestamp

URLs

html_url • URL

api_url • URL

Convenience

recent_push_30d • Checkbox — set by importer (true if recent push in last 30 days)

repo_summary • Long text • AI Autofill → Summarize record

Upsert key: repo_full_name

1.5 Repo Membership (Custom — Junction)

Models the relationship between People and Repos.

Fields

membership_id • Text • Unique ✅ • Required ✅

login • Text • Required ✅

repo_full_name • Text • Required ✅

role • Select (owner | maintainer | contributor | triager) • AI Autofill → Classify record

permission • Select (admin | maintain | write | triage | read)

contributions_past_year • Number

last_activity_at • Timestamp

Upsert key: membership_id

1.6 Signals (Custom — Activity)

Stores GitHub events to time outbound (e.g., recent PRs, issues, stars).

Fields

signal_id • Text • Unique ✅ • Required ✅

signal_type • Select (pr | issue | commit | release | star | fork | other)

signal • Text • AI Autofill → Summarize record

signal_at • Timestamp • Required ✅

url • URL

source • Select (default: GitHub)

repo_full_name • Text (helper field linking to repo)

login • Text (helper field linking to person)

Upsert key: signal_id

2. Relationships

People ↔ Repo Membership ↔ Repos (many-to-many via Membership)

People ↔ Signals (one-to-many)

Repos ↔ Signals (one-to-many)

People ↔ Companies (many-to-one)

Deals ↔ People/Companies (standard CRM relationships)

3. Upsert Keys

People → login

Repos → repo_full_name

Repo Membership → membership_id

Signals → signal_id

Companies → Domains

Deals → Attio default keys (e.g., # Record ID)

4. Import CSV Headers

Repos.csv
repo_full_name,repo_name,owner_login,host,description,primary_language,license,topics,stars,forks,watchers,open_issues,is_fork,is_archived,created_at,updated_at,pushed_at,html_url,api_url,recent_push_30d

People.csv
login,id,node_id,lead_id,name,company,email_profile,email_public_commit,Predicted Email,location,bio,pronouns,public_repos,public_gists,followers,following,created_at,updated_at,html_url,avatar_url,github_user_url,api_url

Membership.csv
membership_id,login,repo_full_name,role,permission,contributions_past_year,last_activity_at

Signals.csv
signal_id,login,repo_full_name,signal_type,signal,signal_at,url,source

5. Key Views

Hot Maintainers (People): repos_maintained_count ≥ 1 AND last_signal_at ≤ 7d

High-Impact Repos (Repos): stars ≥ 500 AND recent_push_30d = true

Fresh Signals (Signals): signal_type in (pr, release) AND signal_at ≤ 72h

6. AI Autofill Guidance

People.Personal Bio Summary → “In 1 sentence, summarize what this maintainer works on and their most notable repo.”

People.Recommended Icebreaker → “Write a tasteful, specific icebreaker using the latest Signal + Repo stars.”

Repos.description / repo_summary → “One-liner of what the repo does, target audience, and differentiation.”

Repos.primary_language (fallback) → “Infer primary language from description/topics when missing.”

Signals.signal → “Turn a raw PR/issue/commit event into a short, human-readable activity line.”

Repo Membership.role → “Infer the person's role from their permissions and activity on the repo.”

7. Automations

Trigger: New Signal (within last 72h) → add Person to “Fresh Maintainers” list + push notification to Slack/Instantly.

Scoring: Use stars_sum_across_repos + followers + recent signals → to prioritize high-value People.

Outbound stats: Engagement metrics (email opens, clicks, replies) → can be logged as Signals (e.g., signal_type=email_open) or tracked via a separate Outbound object.

8. Future Extensions

Add Release Notes (capture semantic diffs for personalization in outreach)

Repo Health metrics (e.g., CI status, issue close ratio for quality)

Auto-link Companies ↔ Repos via organization logins for better rollups

Owner: Growth / lrny
Data Source: GitHub API via Leads scraper
Storage: Attio
Outbound: Instantly
