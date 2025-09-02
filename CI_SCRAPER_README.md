# GitHub CI/DevOps Lead Scraper

## Bottom-up Discovery Approach

This scraper implements your bottom-up strategy for finding CI/DevOps decision makers and practitioners:

**Strategy**: Use GitHub search → find Python repos with real CI activity → map to people

## Quick Start

```bash
# Set your GitHub token
export GITHUB_TOKEN=your_github_token_here

# Run with default settings
python run_ci_scraper.py

# Custom run
python run_ci_scraper.py --max-repos 50 --out my_ci_leads.csv
```

## Search Queries Used

The scraper uses the exact queries you specified:

1. `path:.github/workflows language:YAML pytest pushed:>=2024-06-01`
2. `path:.github/workflows language:YAML "pytest -q" pushed:>=2024-06-01`
3. `path:.github/workflows language:YAML tox pushed:>=2024-06-01`
4. `filename:CODEOWNERS ".github/workflows"`
5. `filename:CODEOWNERS "tests/"`

## Data Extraction Process

For each repo/org found:

### 1. Workflow File Authors

- Extracts commits to `.github/workflows/**` in last 90 days
- Identifies who's actively maintaining CI/CD pipelines

### 2. Test Committers

- Extracts top committers to `tests/**` directories
- Finds the practitioners who really own testing

### 3. CODEOWNERS Parsing

- Parses CODEOWNERS for `.github/workflows` or `tests/**` patterns
- Identifies official maintainers and decision makers

### 4. GitHub → LinkedIn Mapping

- Collects GitHub profile metadata (name, company, location, bio)
- Generates LinkedIn search queries for each lead
- Maps handles to companies via organization membership

## Output: Two Key Lists

### Directors List (Decision Makers)

- Repository admins and maintainers
- Organization members with high permissions
- Users with senior titles in bio (CTO, Director, Lead, Principal, Architect)
- High follower counts (influence indicators)

### Maintainers List (Practitioners)

- Active workflow file contributors
- Heavy test committers
- CODEOWNERS for CI-related paths
- The people who actually own CI/CD in practice

## Usage Strategy

1. **Email Directors First**: They make purchasing decisions
2. **Personalize with Maintainer Data**: Use artifacts from maintainers' repos to personalize director emails
3. **LinkedIn Mapping**: Use generated queries to find LinkedIn profiles
4. **Company Research**: Map to corporate domains for email patterns

## Output Fields

Each lead includes:

**Identity & Contact**

- GitHub username, name, email (if available)
- Company, location, bio
- LinkedIn search query

**Repository Context**

- Repo name, description, stars, language, topics
- How they were discovered (workflow_author, test_committer, codeowner)

**CI/DevOps Signals**

- Workflow commits in last 90 days
- Test commits in last 90 days
- CODEOWNERS patterns they own
- Repository permission level

**Role Classification**

- `director` (decision maker, score ≥60)
- `maintainer` (CI practitioner, score ≥50)
- `contributor` (other)

**Scoring**

- CI Expertise Score (0-100): Based on workflow/test activity
- Decision Maker Score (0-100): Based on permissions/influence
- Overall Score & Tier (A/B/C)

## Examples

```bash
# Basic run
python run_ci_scraper.py

# Target specific number of repos
python run_ci_scraper.py --max-repos 200

# Use custom config
python run_ci_scraper.py --config configs/ci_scraper.yaml

# Dry run to see what would be processed
python run_ci_scraper.py --dry-run

# Save to specific file
python run_ci_scraper.py --out directors_and_maintainers.csv
```

## Configuration

Edit `configs/ci_scraper.yaml` to customize:

- Search queries and filters
- Scoring weights for directors vs maintainers
- Role classification thresholds
- Output formats and fields
- Rate limiting settings

## Rate Limiting

The scraper is designed to be respectful of GitHub's API limits:

- 1 second delay between repos by default
- 0.2 second delay between user profile requests
- Automatic rate limit detection and backoff
- Supports multiple GitHub tokens for higher limits

## Token Requirements

GitHub Personal Access Token with these scopes:

- `repo` (to read repository data)
- `read:user` (to read user profiles)
- `read:org` (to check organization membership)

Get a token at: https://github.com/settings/tokens

## Output Analysis

The scraper provides detailed analytics:

- Role distribution (directors vs maintainers vs contributors)
- Tier distribution (A/B/C quality)
- Signal type distribution (how leads were found)
- Top companies represented
- Average expertise and decision-maker scores

Perfect for identifying your highest-value targets for outbound campaigns focused on CI/DevOps tooling.
