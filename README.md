# 🚀 Open Source Maintainers Outreach System

**Schedule 2,000 emails on Monday with AI-powered personalization, Attio CRM integration, and automated follow-ups.**

## 🏗️ System Overview

This is a complete **agentic sales system** for open source maintainer outreach, combining:

- **🎯 Lead Generation**: GitHub scraper for OSS maintainers
- **📊 CRM Integration**: Attio with custom OSS data model
- **📧 Email Campaigns**: Instantly with 17 Google Workspace domains
- **🎬 Video Personalization**: 87-customized demo videos
- **📋 Project Management**: Linear for deal tracking
- **🤖 AI Automation**: Agentic workflows for personalization and follow-ups

## 🎯 Current Mission: 2,000 Emails on Monday

### 📈 Campaign Goal

- **2,000 emails** sent Monday morning
- **OSS maintainers** with active Python repos
- **Personalized content** using AI and GitHub signals
- **Automated follow-ups** and CRM integration

### 🛠️ Tech Stack

- **Lead Gen**: GitHub API scraper (65+ data fields)
- **CRM**: Attio with custom OSS maintainer model
- **Email**: Instantly with 40-60 warmed Google Workspace inboxes
- **Video**: Personalized demo videos with custom intros
- **Project Mgmt**: Linear for hot lead tracking
- **AI**: Agentic automation for personalization

---

## 🚀 Quick Start (5 minutes)

### 1. **Setup Environment**

```bash
# Install dependencies
pip install -r requirements.txt

# Set GitHub token (required)
export GITHUB_TOKEN=ghp_your_token_here
python test_token.py  # Verify it works
```

### 2. **Generate Leads**

```bash
# Test run (2 repos)
./run_scraper.sh -n 2

# Full run (50 repos)
./run_scraper.sh
```

### 3. **Export to Attio CRM**

```bash
make attio  # Creates CSVs in exports/attio/
```

### 4. **Schedule Email Campaign**

- Import CSV to Instantly
- Connect 40-60 warmed inboxes
- Set Monday 9:30 AM send time
- 2,000 email cap with 50/inbox limit

---

## 📁 System Components

### 🎯 1. GitHub Lead Scraper

**Main file**: `github_prospect_scraper.py`

#### Features

- **65+ data fields** per prospect
- **Email filtering** (only returns prospects with emails)
- **Incremental CSV writing** (updates as prospects are found)
- **Attio-ready exports** (all CRM fields included)
- **Social extraction** (auto-extracts LinkedIn from blog URLs)

#### Quick Commands

```bash
# Test run (2 repos)
./run_scraper.sh -n 2

# Full production run
./run_scraper.sh

# Analyze single user/repo
./scrape_url.sh @username
./scrape_url.sh https://github.com/owner/repo

# Attio export mode
make attio
```

#### Output Files

- `data/prospects_latest.csv` - Latest full export
- `exports/attio/` - Attio-ready CSVs (People.csv, Repos.csv, etc.)
- `data/github_export_YYYYMMDD_HHMMSS/` - Complete GitHub data dumps

### 📊 2. Attio CRM Integration

**Data Model**: [docs/attio-crm-oss-maintainers-model.md](docs/attio-crm-oss-maintainers-model.md)

#### Setup Instructions

1. **Get API Credentials**:

   ```bash
   # Set environment variables
   export ATTIO_API_TOKEN='your_api_key_here'
   export ATTIO_WORKSPACE_ID='your_workspace_id_here'

   # Test connection
   make attio-test
   ```

2. **Create Required Objects**:

   ```bash
   make attio-objects  # Creates People, Repos, Signals, Repo Membership objects
   ```

3. **Run Intelligence Pipeline**:
   ```bash
   make intelligence  # Automatically pushes to Attio
   ```

#### Core Objects

- **People** (OSS maintainers) - 25+ fields including GitHub stats
- **Repos** (GitHub repositories) - Stars, topics, language, activity
- **Signals** (GitHub events) - PRs, issues, commits, releases
- **Repo Membership** (Person ↔ Repo relationships)
- **Companies** (Organizations) - With OSS metrics rollups
- **Deals** (Pipeline opportunities)

#### Import Headers (CSV)

```csv
# People.csv
login,id,node_id,lead_id,name,company,email_profile,email_public_commit,Predicted Email,location,bio,pronouns,public_repos,public_gists,followers,following,created_at,updated_at,html_url,avatar_url,github_user_url,api_url

# Repos.csv
repo_full_name,repo_name,owner_login,host,description,primary_language,license,topics,stars,forks,watchers,open_issues,is_fork,is_archived,created_at,updated_at,pushed_at,html_url,api_url,recent_push_30d

# Signals.csv
signal_id,login,repo_full_name,signal_type,signal,signal_at,url,source
```

### 📧 3. Instantly Email Campaigns

**Integration**: 17 Google Workspace domains, 40-60 warmed inboxes

#### Campaign Setup for Monday 2,000 Emails

1. **Inbox Pool**: 40-60 inboxes across 17 domains (2-3 per domain)
2. **Per-inbox cap**: 50 emails/day (80 max if highly warmed)
3. **Total capacity**: 2,000-3,000 emails Monday
4. **Smart sending**: ON (random gaps, reply detection)
5. **Schedule**: Monday 9:30 AM recipient timezone

#### Email Templates (AI-Generated)

```txt
Subject: tiny PR to fix {{repo}} CI flakes
Hi {{first_name}},

Saw {{repo}} has {{issue_count}} open issues and recent {{language}} commits.
Nova is a small GitHub App that only wakes up when CI fails on a PR,
pinpoints the cause, and pushes a minimal patch as a PR.

Zero lock-in, BYO API key, OSS license. Want a one-off trial on a test PR?

— Sebastian
{{unsub_link}}
```

#### Follow-up Sequence

- **Day 1**: Initial personalized email
- **Day 3**: "Circling back on Nova for {{repo}}..."
- **Day 7**: Final follow-up with demo PR offer

### 🎬 4. Video Personalization System

**Main script**: `video_combiner_with_subtitles.py`

#### Features

- **87 personalized videos** with custom intros
- **Overlay approach**: Intro video + base video audio/subtitles
- **36-second intros** with clean backgrounds
- **Batch processing** for all videos
- **Subtitle preservation** from base video

#### Workflow

```bash
# Place 87 intro videos in data/intros/
# Run combiner
./run_video_combiner.sh

# Output: data/combined_videos/personalized_demo_01.mp4 through _87.mp4
```

### 📋 5. Linear Project Management

**Integration**: Automated task creation for hot leads

#### Automation Flow

1. **Instantly reply** → Attio upsert → Stage = Interested
2. **Attio trigger** → Linear issue created
3. **Task details**:
   - Title: `Reply: {{first_name}} @ {{company}} wants trial`
   - Body: Full reply + link to thread
   - Assignee: Sebastian
   - Due: +2 days
   - Labels: OSS, Inbound

### 🤖 6. AI Agentic Automation

**Current AI Integration**:

- **Repo intelligence**: Analyze GitHub signals for personalization
- **Copy generation**: AI-crafted subjects and email variants
- **Intent classification**: Reply analysis (interested/technical/not-now)
- **Follow-up drafting**: AI-generated responses

**Future Agentic Features**:

- **Auto-demo PRs**: Fork repos, fix failing tests, create PRs
- **Reply handling**: Automated responses to common questions
- **Lead scoring**: ML-based prioritization
- **Campaign optimization**: A/B testing and variant generation

---

## 📧 Monday 2,000 Email Campaign

### 🎯 Campaign Blueprint

#### **Pre-flight Checklist**

- ✅ **DNS/SPF/DKIM/DMARC**: All 17 domains configured
- ✅ **Inbox Pool**: 40-60 Google Workspace inboxes (2-3 per domain)
- ✅ **Warm-up Status**: Minimum 2 weeks of warm-up activity
- ✅ **Lead Data**: 2,400 prospects (20% buffer for bounces)
- ✅ **Attio Setup**: Objects and automations configured
- ✅ **Linear Setup**: Project and automation rules ready

#### **Volume Math**

```
40 inboxes × 50 emails/day = 2,000 emails
50 inboxes × 40 emails/day = 2,000 emails (backup plan)
60 inboxes × 33 emails/day = ~2,000 emails (emergency)
```

#### **Send Strategy**

- **Time**: Monday 9:30 AM (recipient timezone)
- **Window**: 9:30 AM - 4:30 PM (7-hour window)
- **Smart Sending**: ON (random gaps 30-120 seconds)
- **Reply Detection**: ON (stop sequence on any reply)
- **Daily Caps**: 50/inbox (80 if highly warmed)

#### **AI-Powered Personalization**

**Repo Intelligence Pipeline**:

1. **Input**: GitHub repo URL + maintainer data
2. **AI Analysis**: Recent commits, CI failures, issue patterns
3. **Output**: Personalized snippets + subject variants

**Example AI-Generated Content**:

```json
{
  "personalization_snippet": "noticed CI flakes on Windows for pytest in {{repo}}; we can patch the failing test",
  "subject_options": [
    "tiny PR to fix {{repo}} CI flakes",
    "keeps {{repo}} green—no yak shaving",
    "auto-fix failing pytest in {{repo}}"
  ],
  "body_variant": "Built a small GitHub App that wakes only when CI fails..."
}
```

#### **Automation Chain**

**Email Reply Flow**:

```
Instantly Reply → Attio Webhook → Stage = Interested → Linear Issue
```

**Linear Task Creation**:

- **Title**: `Reply: Riley @ Acme wants trial on repo/project`
- **Body**: Full reply + thread link + suggested next steps
- **Assignee**: Sebastian
- **Due Date**: +2 business days
- **Labels**: OSS, Inbound, Hot

#### **Contingency Plans**

**If Inboxes Fail**:

- Reduce per-inbox cap to 40 (maintains 2,000 total)
- Add backup inboxes (keep 10 extras connected)
- Split into AM/PM waves if needed

**If Lead Quality Issues**:

- AI scoring filter: Only send to prospects with activity < 30 days
- Domain diversity: Rotate across all 17 domains
- Timezone targeting: Send during business hours

---

## 🤖 Agentic Sales Alternatives

### 🎯 **Current Stack Analysis**

Your system is already **highly agentic**:

- **GitHub scraper** = Lead generation agent
- **Attio** = CRM intelligence agent
- **Instantly** = Outreach execution agent
- **Linear** = Task management agent

### 🚀 **Level 2: Enhanced AI Integration**

#### **Auto-Demo PR Agent**

```python
# Future agent that creates demo PRs automatically
def create_demo_pr(repo_url, maintainer_email):
    # 1. Fork repository
    # 2. Analyze failing tests
    # 3. Generate minimal fix
    # 4. Create and submit PR
    # 5. Notify maintainer
```

#### **Reply Intelligence Agent**

- **Intent Classification**: interested | technical | not-now | unsubscribe
- **Auto-Response Generation**: Drafts replies to common questions
- **Follow-up Timing**: Optimizes send timing based on engagement patterns

#### **Campaign Optimization Agent**

- **A/B Testing**: Tests subject lines, send times, email lengths
- **Performance Analysis**: Tracks open rates, reply rates, bounce rates
- **Variant Generation**: Creates new email templates based on winners

### 🌟 **Level 3: Full Autonomous Operation**

#### **End-to-End Sales Agent**

```
Lead Discovery → Qualification → Outreach → Nurture → Close
```

**Autonomous Workflow**:

1. **Discovery**: Scans GitHub for new repos matching ICP
2. **Qualification**: AI scores and segments prospects
3. **Outreach**: Sends personalized sequences
4. **Nurture**: Handles replies and follow-ups
5. **Close**: Creates deals and schedules demos

#### **Real-Time Adaptation**

- **Signal Processing**: Monitors GitHub activity for trigger events
- **Competitive Intelligence**: Tracks when competitors engage prospects
- **Market Signals**: Adjusts messaging based on trending topics

### 🔧 **Implementation Options**

#### **Option A: Enhance Current Stack**

- Add AI layers to existing tools
- Keep human oversight for high-touch moments
- Gradual automation of repetitive tasks

#### **Option B: Agentic Sales Platform**

Consider platforms like:

- **Replicant** (agentic sales)
- **Outreach.ai** (AI sales development)
- **Salesforce Einstein** (CRM AI)
- **HubSpot AI** (marketing automation)

#### **Option C: Custom AI Agent Framework**

Build on top of your current stack:

- **LangChain** for agent orchestration
- **OpenAI GPT-4** for content generation
- **Zapier/Make** for workflow automation
- **Custom ML models** for lead scoring

### 📊 **Success Metrics for Agentic Sales**

#### **Efficiency Metrics**

- **Time to first reply**: Target < 24 hours
- **Qualified leads/week**: Scale to 50-100
- **Automation coverage**: 80% of routine tasks

#### **Quality Metrics**

- **Reply rate**: Target 3-5%
- **Qualified reply rate**: Target 40% of replies
- **Demo booking rate**: Target 20% of qualified replies

---

## 🛠️ Advanced Configuration

### 🎯 ICP (Ideal Customer Profile) Setup

**File**: `configs/icp/options.yaml`

Current ICPs configured:

- **ICP01**: PyPI Maintainers – Fast-moving Python libraries
- **ICP02**: ML/Data Science ecosystem maintainers
- **ICP03**: Seed/Series A Python SaaS (Actions-first)
- **ICP04**: API/SDK DevTools teams
- **ICP05**: University/Research labs

### ⚙️ Main Configuration

**File**: `configs/main.yaml`

```yaml
search:
  type: repositories
  query: "language:python stars:50..2000 is:public archived:false in:readme pytest pushed:>={date:60}"
  sort: updated
  order: desc

filters:
  activity_days: 90
  skip_without_email: true

limits:
  max_repos: 100
  per_repo_prs: 15
  max_people: 20
```

### 🤖 Agent Configuration

**Future**: Agent orchestration config

```yaml
agents:
  lead_generation:
    schedule: "0 */4 * * *" # Every 4 hours
    sources: ["github", "pypi", "reddit"]
    filters: ["activity_30d", "email_verified"]

  personalization:
    model: "gpt-4"
    templates: ["technical", "business", "academic"]
    variants: 3

  outreach:
    sequences: ["cold", "warm", "nurture"]
    channels: ["email", "linkedin", "twitter"]
```

---

## 📊 Monitoring & Analytics

### 🎯 Campaign Performance Dashboard

**Key Metrics**:

- **Send Success Rate**: Target > 98%
- **Inbox Placement**: Primary > 80%
- **Open Rate**: Target 25-35%
- **Reply Rate**: Target 3-5%
- **Qualified Reply Rate**: Target 40%

### 🔍 AI Agent Performance

**Agent Metrics**:

- **Personalization Quality**: A/B test conversion rates
- **Reply Classification Accuracy**: Target > 90%
- **Auto-Response Satisfaction**: Survey-based scoring

### 📈 Scaling Projections

**Current Capacity**: 2,000 emails/day
**Week 1 Goal**: 2,000 emails Monday
**Month 1 Goal**: 10,000 emails/week
**Year 1 Goal**: 50,000 emails/month

---

## 🆕 URL Mode - Quick Prospect Analysis

Analyze any GitHub user or repository instantly:

### Analyze a GitHub user profile

```bash
# Using the wrapper script (easiest)
./scrape_url.sh @username
./scrape_url.sh https://github.com/username

# Using the main script directly
python github_prospect_scraper.py --url "https://github.com/username" --print-only
```

### Analyze contributors to a specific repository

```bash
./scrape_url.sh https://github.com/owner/repo
python github_prospect_scraper.py --url "https://github.com/owner/repo" --print-only
```

### Save results to CSV

```bash
./scrape_url.sh @username --save
python github_prospect_scraper.py --url "https://github.com/username" --out prospects.csv
```

**Example Output:**

```
📊 PROSPECT SUMMARY (1 total)
================================================================================

  1. username (Full Name)
    📧 Email: maintainer@example.com
    🏢 Company: Acme Corp
    📍 Location: San Francisco
    🔗 LinkedIn: linkedin.com/in/username
    ⭐ GitHub Stats: 1.2k followers, 45 repos
    📦 Repository: owner/repo (2.1k stars)
    🎯 Signal: opened PR #123: Fix CI pipeline
    📅 Activity: 2024-01-15T14:30:00Z
```

## 📊 Data Output Formats

### CSV Export Schema

The scraper generates comprehensive CSV files with these columns:

**Core Prospect Data**:

- `lead_id` - Unique identifier (hash of user + repo)
- `login` - GitHub username
- `name` - Full name (if public)
- `company` - Company (if public)
- `email_public_commit` - Email from commits
- `Predicted Email` - AI-generated email predictions

**Repository Context**:

- `repo_full_name` - Repository they contributed to
- `repo_name` - Repository name
- `owner_login` - Repository owner
- `topics` - Repo topics (comma-separated)
- `language` - Primary programming language
- `stars` - Repository star count
- `forks` - Repository fork count

**Activity Signals**:

- `signal` - What they did (PR title or commit message)
- `signal_type` - 'pr', 'commit', 'issue', 'release'
- `signal_at` - When they did it (ISO timestamp)

**Social & Enrichment**:

- `location` - Geographic location
- `bio` - GitHub bio
- `LinkedIn` - Auto-extracted LinkedIn URL
- `followers` - GitHub follower count
- `public_repos` - Number of public repositories

**Attio Integration Fields**:

- All fields map directly to Attio OSS maintainer data model
- Automatic relationship creation between People ↔ Repos ↔ Signals
- Ready for CRM import and automation triggers

## 🎯 Search Query Examples

### AI/ML Ecosystem

```yaml
query: "language:python topic:machine-learning topic:ai stars:>50 pushed:>2024-01-01"
```

### JavaScript/React Stack

```yaml
query: "language:javascript (react OR nextjs OR vue) stars:>100 pushed:>2024-01-01"
```

### DevOps/Infrastructure

```yaml
query: "topic:kubernetes topic:devops topic:infrastructure stars:>200 pushed:>2024-01-01"
```

### API/SDK Development

```yaml
query: "language:python (sdk OR client OR api) in:name stars:>50 pushed:>2024-01-01"
```

### Data Science & Analytics

```yaml
query: "language:python topic:data-science (pandas OR numpy OR scipy) stars:>100"
```

## ⚡ Scaling & Optimization

### **Multi-Segment Campaigns**

Create different configs for each ICP:

```bash
# AI/ML prospects
python github_prospect_scraper.py --config configs/icp/icp02_ml_ds_maintainers.yaml --out ai-prospects.csv

# PyPI maintainers
python github_prospect_scraper.py --config configs/icp/icp01_pypi_maintainers.yaml --out pypi-prospects.csv

# DevTools
python github_prospect_scraper.py --config configs/icp/icp04_api_sdk_tooling.yaml --out devtools-prospects.csv
```

### **Automated Scheduling**

Set up cron jobs for continuous lead generation:

```bash
# Daily lead refresh (6 AM)
0 6 * * * cd /Users/seb/leads && ./run_scraper.sh

# Weekly deep scan (Sunday 2 AM)
0 2 * * 0 cd /Users/seb/leads && python github_prospect_scraper.py --config config-deep.yaml
```

### **Rate Limit Management**

- **Authenticated requests**: 5,000/hour (vs 60 unauthenticated)
- **Automatic backoff**: Built-in exponential backoff
- **Parallel processing**: Multiple configs run simultaneously
- **Resume capability**: Picks up where it left off

### **Email Enrichment Pipeline**

After scraping, enhance your data:

1. **Email Discovery**: Hunter.io, Clearbit, Apollo, ZoomInfo
2. **Social Matching**: LinkedIn, Twitter, personal websites
3. **Corporate Lookup**: Company domains + role-based emails
4. **Validation**: MX record checking, bounce prevention

---

## 🛠️ Troubleshooting

### **Rate Limit Errors**

```bash
# Check your limits
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/rate_limit

# Solutions:
# 1. Verify token has 'repo' scope
# 2. Reduce --max-repos limit
# 3. Add longer delays between requests
# 4. Use multiple tokens if available
```

### **No Results Found**

- **Query too narrow**: Remove specific terms, lower star thresholds
- **Date range too recent**: Extend `pushed:>` date back further
- **Token issues**: Verify token permissions and regeneration
- **Rate limiting**: Wait for reset or use different token

### **Missing Emails**

- **Normal situation**: Most GitHub users hide emails
- **Solutions**: Use enrichment services, focus on signals for personalization
- **Alternative**: Target repos with public maintainer emails in commits

### **Attio Import Issues**

- **Schema mismatch**: Verify CSV headers match Attio object fields
- **Upsert keys**: Ensure unique identifiers are present and correct
- **Data types**: Check number fields don't contain text, dates are ISO format

---

## 🎯 Next Steps & Roadmap

### **Immediate Actions (This Week)**

- [ ] Set up GitHub token and test scraper
- [ ] Run sample scrape with 2-3 repos
- [ ] Configure Attio objects and import test data
- [ ] Set up Instantly campaign with 2-3 test inboxes
- [ ] Schedule Monday 2,000 email campaign

### **Short Term (Next Month)**

- [ ] Implement AI personalization pipeline
- [ ] Set up Linear automation for hot leads
- [ ] Create 87 personalized video intros
- [ ] Establish monitoring dashboard
- [ ] Optimize email deliverability across domains

### **Long Term (3-6 Months)**

- [ ] Build auto-demo PR generation system
- [ ] Implement reply intelligence and auto-responses
- [ ] Scale to 50,000 emails/month
- [ ] Add predictive lead scoring
- [ ] Integrate additional channels (LinkedIn, Twitter)

---

## 📞 Support & Resources

### **Documentation**

- [Attio OSS Data Model](docs/attio-crm-oss-maintainers-model.md)
- [Video System Guide](VIDEO_COMBINER_README.md)
- [Release Notes](RELEASE_NOTES_v0.6.1.md)

### **Key Files**

- `config.yaml` - Main scraper configuration
- `configs/icp/options.yaml` - ICP definitions
- `Makefile` - Automation shortcuts
- `requirements.txt` - Python dependencies

### **Quick Commands Reference**

```bash
# Setup
make install && export GITHUB_TOKEN=your_token

# Test run
./run_scraper.sh -n 2

# Production run
./run_scraper.sh

# Attio export
make attio

# URL analysis
./scrape_url.sh @username
```

---

## 🚀 Ready to Launch?

Your system is **production-ready** for the Monday 2,000 email campaign. The combination of:

- **GitHub scraper** → **Attio CRM** → **Instantly campaigns** → **Linear tasks**

...creates a complete agentic sales system that can scale from 2,000 emails/day to 50,000/month.

**Next**: Run `./run_scraper.sh` to generate your first batch of leads, then import to Instantly for Monday's launch!

---

_Built for Open Source Maintainers • Powered by AI • Scaled to 50K emails/month_

## 📋 CLI Reference

**Main Commands:**

```bash
# Quick test
./run_scraper.sh -n 2

# Full production run
./run_scraper.sh

# Attio export
make attio

# URL analysis
./scrape_url.sh @username
```

---

## ⚖️ Compliance & Ethics

### **✅ Best Practices**

- **Legitimate outreach** to developers and maintainers
- **Rate limit respect** with automatic backoff
- **Opt-out compliance** with instant unsubscribe
- **Value-first approach** - provide genuine help
- **CAN-SPAM compliance** with physical address and unsubscribe

### **❌ Never Do**

- Spam or bulk unsolicited emails
- GitHub issues/PRs for sales pitches
- Private repository scraping
- GitHub Terms of Service violations
- Misrepresentation or hype

---

## 📈 Success Metrics

**Campaign Performance:**

- **Send Success**: >98% delivery rate
- **Primary Inbox**: >80% placement
- **Open Rate**: 25-35% (industry excellent)
- **Reply Rate**: 3-5% (strong for cold outreach)
- **Qualified Reply Rate**: 40%+ of replies

**Lead Quality:**

- **Active Maintainers**: Recent commits (<30 days)
- **High-Impact Repos**: Stars >500, active community
- **Technical Alignment**: pytest, CI, active development

---

## 🚀 Ready to Launch?

Your **agentic sales system** is **production-ready** for the Monday 2,000 email campaign!

**🎯 Next Steps:**

1. Run `./run_scraper.sh` to generate leads
2. Import to Instantly with your 40-60 warmed inboxes
3. Schedule Monday 9:30 AM campaign
4. Watch replies auto-sync to Attio → Linear tasks

**📞 Questions?** All documentation is above - you have everything needed to launch and scale!

---

_Built for Open Source Maintainers • Powered by AI • Scaled to 50K emails/month_

```bash
# Regular config-based scraping
python github_prospect_scraper.py --config config.yaml --out prospects.csv

# URL mode for quick analysis
python github_prospect_scraper.py --url "https://github.com/username" --print-only

# Override config limits
python github_prospect_scraper.py --config config.yaml -n 5 --out prospects.csv

# All options
python github_prospect_scraper.py --help
```

**Available Options:**

- `--config CONFIG` - Config file path (default: config.yaml)
- `--out OUT` - Output CSV path (default: data/prospects.csv)
- `-n, --max-repos MAX_REPOS` - Maximum repos to process (overrides config)
- `--url URL` - GitHub URL to scrape (user profile or repository)
- `--print-only` - Only print results, don't save to CSV
- `--dedup-db` - Path to SQLite DB for dedup (default: data/dedup.db)
- `--no-dedup` - Disable deduplication (process all logins)
- `--timeout-secs` - HTTP request timeout seconds (default: 15)

### Environment

- `DEDUP_DB` (optional): absolute path to the SQLite dedup DB. If set, it becomes the default for `--dedup-db`.
- `HTTP_TIMEOUT_SECS` (optional): default timeout for HTTP requests, used if `--timeout-secs` is not passed.

Example:

```bash
export DEDUP_DB="$(pwd)/data/dedup.db"
export HTTP_TIMEOUT_SECS=20
python github_prospect_scraper.py --config configs/main.yaml --out data/prospects.csv
```

## Good Citizen Guidelines

✅ **DO:**

- Use for legitimate outreach to developers
- Respect rate limits and add delays
- Honor opt-outs and unsubscribes
- Focus on providing value

❌ **DON'T:**

- Spam or send bulk unsolicited emails
- Open GitHub issues for sales
- Scrape private repos or data
- Violate GitHub ToS

## Troubleshooting

### Rate limit errors

- Check your rate limit: `curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/rate_limit`
- Use authenticated requests (set GITHUB_TOKEN)
- Reduce `per_page` and add longer `delay`

### No results

- Make your search query less restrictive
- Increase `activity_days` to look further back
- Check if your token has the right permissions

### Missing emails

- This is normal - most users don't expose emails
- Use email enrichment services
- Focus on the signals and repos for context

## Next Steps

1. **Enrich the data** - Add emails, LinkedIn, company info
2. **Score the leads** - Rank by repo relevance, contribution recency
3. **Personalize outreach** - Use the signal data for context
4. **Track results** - A/B test different approaches

## Related Docs

- See the Attio CRM data model for OSS maintainers: [docs/attio-crm-oss-maintainers-model.md](docs/attio-crm-oss-maintainers-model.md)

## Attio exports

This repository can emit both a flat CSV and split CSVs for Attio.

Flat (unchanged):

```bash
GITHUB_TOKEN=... python github_prospect_scraper.py --config config.yaml --out data/prospects.csv
```

Split for Attio (People/Repos/Memberships/Signals):

```bash
GITHUB_TOKEN=... python github_prospect_scraper.py --config config.yaml \
  --out data/prospects.csv \
  --out-dir data
```

URL mode (single user/repo):

```bash
python github_prospect_scraper.py --url https://github.com/pytorch/benchmark --out-dir data
```

See `docs/attio-crm-oss-maintainers-model.md` for object definitions, upsert keys, and headers.

## Example Integration

```python
# Load prospects
import pandas as pd
prospects = pd.read_csv('prospects.csv')

# Filter high-value prospects
ai_prospects = prospects[
    (prospects['topics'].str.contains('ai|ml|llm', case=False)) &
    (prospects['stars'] > 500)
]

# Group by repo for batch outreach
by_repo = prospects.groupby('repo_full_name').agg({
    'login': 'count',
    'signal': lambda x: x.iloc[0]  # Most recent signal
}).sort_values('login', ascending=False)
```

## Full GitHub Export (Attio-ready)

Use the one-file runner to export everything for a user or org and generate Attio CSVs (optional):

```bash
export GITHUB_TOKEN=ghp_yourtoken
./github_full_export.sh --account vercel --attio
# or include commits (heavy) and cap per repo
./github_full_export.sh --account username --include-commits --max-commits-per-repo 1000
```

Outputs in `data/export_<account>_<timestamp>/`:

- raw/: JSONL per entity
- csv/: normalized CSVs (repositories, issues, pulls, releases, contributors, stargazers, topics, languages, ...)
- attio/: `People.csv`, `Companies.csv`, and `README_ATTIO.md` (when `--attio`)
