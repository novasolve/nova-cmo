# GitHub Prospect Scraper 🎯

A clean, scalable GitHub scraper that finds prospects based on their recent contributions to repos matching your criteria.

## What it does

1. **Searches GitHub** for repos matching your filters (language, topics, stars, activity)
2. **Extracts contributors** who recently opened PRs or made commits
3. **Captures signals** - what they did and when (e.g., "opened PR #234: add webhook retry")
4. **Exports to CSV** with all the data you need for personalized outreach

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set your GitHub token

```bash
export GITHUB_TOKEN=ghp_yourtoken
```

Get a token at: https://github.com/settings/tokens (needs `public_repo` scope)

### 3. Configure your search

Edit `config.yaml` to target your ideal prospects:

```yaml
search:
  query: "language:python topic:ai stars:>100 pushed:>2024-01-01"
  sort: "updated"
```

### 4. Run the scraper

```bash
python github_prospect_scraper.py --config config.yaml --out prospects.csv
```

## 🆕 URL Mode - Quick Prospect Analysis

Analyze any GitHub user or repository instantly:

### Analyze a GitHub user profile

```bash
# Using the wrapper script (easiest)
./scrape_url.sh @aml5600
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

 1. aml5600 (Andrew Leonard)
    📧 Email: No email found
    🏢 Company: Not specified
    📍 Location: Atlanta
    🔗 LinkedIn: Not found
    ⭐ GitHub Stats: 4 followers, 14 repos
    📦 Repository: aml5600/ModelingToolkit.jl (0 stars)
    🎯 Signal: owns repository: ModelingToolkit.jl
    📅 Activity: 2025-05-11T09:32:53Z
```

## Output Format

The scraper generates a CSV with these columns:

- `lead_id` - Unique identifier (hash of user + repo)
- `login` - GitHub username
- `name` - Full name (if public)
- `company` - Company (if public)
- `email_public_commit` - Email (if found in commits)
- `repo_full_name` - Repository they contributed to
- `signal` - What they did (PR title or commit message)
- `signal_type` - 'pr' or 'commit'
- `signal_at` - When they did it
- `topics` - Repo topics (comma-separated)
- `language` - Primary repo language
- `stars` - Repo star count

## Search Query Examples

### AI/ML Developers

```yaml
query: "language:python topic:machine-learning topic:ai stars:>50 pushed:>2024-01-01"
```

### JavaScript/React Developers

```yaml
query: "language:javascript (react OR nextjs) stars:>100 pushed:>2024-01-01"
```

### DevOps Engineers

```yaml
query: "topic:kubernetes topic:devops topic:infrastructure stars:>200"
```

### Blockchain Developers

```yaml
query: "topic:blockchain topic:web3 topic:ethereum stars:>100"
```

## Scaling Tips

### 1. Run multiple searches

Create different configs for each segment:

```bash
python github_prospect_scraper.py --config config-ai.yaml --out ai-prospects.csv
python github_prospect_scraper.py --config config-web3.yaml --out web3-prospects.csv
```

### 2. Schedule weekly runs

Add to cron to catch new contributors:

```bash
0 0 * * 0 cd /path/to/growth && python github_prospect_scraper.py
```

### 3. Respect rate limits

- The scraper handles rate limiting automatically
- Default delay between requests: 1 second
- Exponential backoff on errors

### 4. Enrich emails

Most GitHub users hide emails. After scraping:

1. Use email enrichment services (Hunter.io, Clearbit, Apollo)
2. Match GitHub usernames to LinkedIn/Twitter
3. Use the company field to find corporate emails

## Configuration Options

### Search Parameters

- `query` - GitHub search syntax
- `sort` - How to sort results (stars/forks/updated)
- `order` - desc or asc
- `per_page` - Results per API call (max 100)

### Filters

- `activity_days` - Only include contributions from last N days

### Limits

- `max_repos` - Maximum repos to analyze
- `per_repo_prs` - PR authors per repo
- `per_repo_commits` - Commit authors per repo
- `max_people` - Total prospect limit

## CLI Options

The scraper supports multiple modes and options:

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
