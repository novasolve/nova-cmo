# GitHub Prospect Scraper

A sophisticated, enterprise-grade GitHub data collection tool for lead intelligence and ICP (Ideal Customer Profile) discovery. Built for scaling from 100 to 100,000+ prospects with intelligent deduplication, concurrent processing, and comprehensive data enrichment.

## 🎯 Overview

The GitHub Prospect Scraper is a powerful tool designed to discover and enrich developer prospects from GitHub repositories. It targets maintainers, contributors, and active developers who match your Ideal Customer Profile (ICP), providing rich data for lead intelligence and outbound sales campaigns.

### Key Features

- 🔍 **Intelligent Repository Discovery**: Advanced GitHub search with dynamic query building
- 👥 **Multi-layered Prospect Collection**: Maintainers, core contributors, and PR authors
- 🔄 **Concurrent Processing**: Parallel repository and user processing with rate limiting
- 🧠 **Smart Deduplication**: Database-backed deduplication across scraping sessions
- 🎯 **ICP-based Filtering**: Configurable scoring and filtering based on ICP criteria
- 📊 **Comprehensive Enrichment**: GitHub profile data, contribution stats, and contact information
- 🛡️ **Compliance-Ready**: Built-in compliance filtering and risk assessment
- 📈 **Analytics & Tracking**: Job tracking with detailed statistics and progress monitoring
- 🔧 **Enterprise Scalability**: Token rotation, rate limit handling, and production-ready architecture

## 🏗️ Architecture

### Core Components

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   GitHub API    │───▶│   Scraper Core  │───▶│   Enrichment    │
│   Integration   │    │                 │    │   Pipeline      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Rate Limiting │    │   Concurrent    │    │   Data Export   │
│   & Token Mgmt  │    │   Processing    │    │   & CRM Sync    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Data Flow

1. **Repository Discovery**: Search GitHub using advanced queries
2. **Prospect Extraction**: Identify maintainers, contributors, and active developers
3. **Profile Enrichment**: Collect comprehensive user and repository data
4. **ICP Scoring**: Apply ICP-based filtering and scoring
5. **Deduplication**: Remove duplicates using database-backed tracking
6. **Export**: Generate CSV, JSON, and CRM-ready formats

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- GitHub Personal Access Token (with `read:user` and `repo` scopes)
- SQLite3 (for deduplication)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd leads

# Install dependencies
pip install -r requirements.txt

# Set up GitHub token
export GITHUB_TOKEN=your_github_token_here
```

### Basic Usage

```bash
# Simple repository search and prospect collection
python github_prospect_scraper.py --query "language:python stars:>1000" --max-repos 50

# Use ICP configuration
python github_prospect_scraper.py --config configs/icp/llm_devtools.yml --output prospects.csv

# Multi-segment scraping with custom config
python github_prospect_scraper.py --config configs/icp/main.yaml --run-all-segments
```

## ⚙️ Configuration

### Configuration Files

The scraper supports multiple configuration formats:

#### YAML Configuration (Recommended)

```yaml
version: 1.0

# Search parameters
search:
  query: "language:python stars:100..2000 pushed:>2024-01-01"
  sort: "updated"
  order: "desc"
  per_page: 30

# Filtering criteria
filters:
  activity_days: 90
  min_contributions: 5
  require_email: true

# Processing limits
limits:
  max_repos: 100
  per_repo_prs: 10
  per_repo_commits: 10
  max_people: 500

# Deduplication settings
dedup:
  enabled: true
  db_path: "data/dedup.db"

# Rate limiting
delay: 1.0
http:
  timeout_secs: 30

# Concurrent processing
concurrency:
  enabled: true
  max_workers: 4
  requests_per_hour: 5000
  cache_dir: ".cache"
```

#### ICP-Specific Configuration

```yaml
# ICP Configuration for LLM Development Tools
version: 1.0

include_topics:
  - llm
  - mcp
  - rag
  - observability

exclude_topics:
  - tutorial
  - docs
  - awesome-list

languages:
  - python
  - typescript
  - go

min_stars: 100
window_days: 30

# Geographic targeting
geo_allow: ["US", "CA", "EU"]
geo_block: ["CN", "RU"]

# Scoring configuration
scoring_weights:
  maintainer: 35
  org_member: 25
  contactable: 20
  icp_match: 15

tier_thresholds:
  A: 70
  B: 55
  C: 40
```

### Command Line Options

```bash
# Basic options
--config CONFIG        Path to YAML configuration file
--query QUERY          GitHub search query (overrides config)
--output OUTPUT        Output CSV file path
--max-repos N          Maximum repositories to process
--leads N              Target number of leads with emails

# Advanced options
--no-dedup            Disable deduplication
--dedup-db PATH       Custom deduplication database path
--timeout-secs N      HTTP timeout in seconds
--run-all-segments    Process all ICP segments
--verbose             Enable verbose logging

# Development options
--dry-run             Show what would be processed without executing
--debug               Enable debug mode with detailed logging
```

## 📊 Data Collection

### Prospect Data Fields

The scraper collects comprehensive data for each prospect:

#### Core Identification

- `lead_id`: Unique identifier (hash of login + repo)
- `login`: GitHub username
- `id`: GitHub user ID
- `node_id`: GraphQL node ID

#### Personal Information

- `name`: Full name from GitHub profile
- `company`: Company/organization
- `email_public_commit`: Email from public commits
- `email_profile`: Email from GitHub profile
- `location`: Geographic location
- `bio`: User biography

#### Repository Context

- `repo_full_name`: Repository name (owner/repo)
- `repo_description`: Repository description
- `signal`: How they were discovered (maintainer, contributor, etc.)
- `signal_type`: Type of contribution
- `topics`: Repository topics/tags
- `language`: Primary programming language

#### Activity & Engagement

- `is_maintainer`: Whether user is a repository maintainer
- `is_org_member`: Organization membership status
- `commit_count_90d`: Commits in last 90 days
- `contributions_last_year`: Total contributions
- `followers`: Number of followers
- `following`: Number of users followed

#### Contact & Enrichment

- `contactability_score`: 0-100 contactability rating
- `email_type`: Type of email (personal, corporate, etc.)
- `is_disposable_email`: Whether email is from disposable provider
- `corporate_domain`: Extracted corporate domain
- `linkedin_query`: Suggested LinkedIn search query

#### Scoring & Compliance

- `prospect_score`: 0-100 overall score
- `prospect_tier`: A/B/C tier classification
- `compliance_risk_level`: Low/Medium/High compliance risk
- `geo_location`: Geographic compliance assessment

## 🔧 Advanced Features

### Concurrent Processing

Enable parallel processing for better performance:

```python
concurrency:
  enabled: true
  max_workers: 4
  requests_per_hour: 5000
  cache_dir: ".cache"
```

### Token Rotation

Handle multiple GitHub tokens for increased rate limits:

```bash
# Set primary token
export GITHUB_TOKEN=ghp_your_primary_token

# Set backup tokens
export GITHUB_TOKEN_2=ghp_backup_token_2
export GITHUB_TOKEN_3=ghp_backup_token_3
```

### Intelligent Deduplication

Database-backed deduplication prevents processing the same user multiple times:

```python
# Deduplication is enabled by default
dedup:
  enabled: true
  db_path: "data/dedup.db"
```

### Rate Limit Handling

Automatic rate limit detection and token rotation:

```
⚠️  GitHub API rate limit: 50/5000 remaining. Resets in 45.2 minutes
🚫 GitHub rate limit exceeded! Rotating to backup token...
✅ Successfully rotated to backup token GITHUB_TOKEN_2
```

### ICP-Based Scoring

Advanced scoring based on ICP criteria:

```python
# Scoring weights
scoring_weights = {
    'maintainer': 35,      # Repository maintainer
    'org_member': 25,      # Organization member
    'contactable': 20,     # Has contact information
    'icp_match': 15,       # Matches ICP criteria
    'stars_velocity': 5,   # Repository growth rate
}
```

## 📈 Output Formats

### CSV Export

Standard CSV format with all prospect fields:

```bash
python github_prospect_scraper.py --config config.yml --output prospects.csv
```

### Attio Integration

Exports data in Attio-compatible format:

```python
# Automatically generates:
# - people_records.json (contact data)
# - repo_records.json (repository data)
# - membership_records.json (relationships)
# - signal_records.json (engagement signals)
```

### JSON Export

Comprehensive JSON format with nested data:

```json
{
  "prospect": {
    "lead_id": "abc123...",
    "login": "johndoe",
    "personal_info": {...},
    "repository_context": {...},
    "scoring": {...}
  }
}
```

## 🔗 API Integrations

### GitHub API v3 + GraphQL

- **Search API**: Repository and code search
- **REST API**: User profiles, repositories, commits
- **GraphQL API**: Advanced queries and batch operations

### Rate Limiting Strategy

- **Primary Token**: Main processing token
- **Backup Tokens**: Automatic rotation on rate limit
- **Smart Backoff**: Exponential backoff with jitter
- **Request Batching**: Minimize API calls through caching

### Webhook Support

Future integration with GitHub webhooks for real-time updates:

```python
# Planned webhook handlers
- repository_push (activity tracking)
- pull_request_opened (contributor identification)
- issues_created (signal detection)
```

## 📊 Analytics & Monitoring

### Job Tracking

Comprehensive job statistics and monitoring:

```python
job_stats = {
    "job_id": "job_20240115_143022",
    "start_time": "2024-01-15T14:30:22Z",
    "duration_seconds": 1847,
    "total_repos_processed": 127,
    "raw_prospects_found": 892,
    "prospects_with_emails": 234,
    "cache_hits": 45,
    "cache_misses": 82,
    "errors": []
}
```

### Performance Metrics

- **Throughput**: Prospects per minute
- **Success Rate**: Percentage of successful API calls
- **Cache Hit Rate**: Percentage of cached requests
- **Duplicate Rate**: Percentage of deduplicated prospects

## 🛡️ Compliance & Security

### Data Privacy

- **GDPR Compliance**: EU data protection standards
- **CCPA Compliance**: California privacy regulations
- **Data Minimization**: Only collect necessary data
- **Right to Deletion**: Easy data removal capabilities

### Compliance Filtering

Built-in compliance and risk assessment:

```python
compliance_filters = {
    "blocked_companies": ["company_a", "company_b"],
    "blocked_email_domains": ["spam.com", "temp-mail.org"],
    "prohibited_bio_terms": ["undesirable_term"],
    "geo_block": ["CN", "RU", "IR"]
}
```

### Security Features

- **Token Encryption**: Secure token storage
- **Audit Logging**: Comprehensive activity logging
- **Data Sanitization**: Automatic data cleaning and validation
- **Access Control**: Role-based access management

## 🚨 Troubleshooting

### Common Issues

**Rate Limit Errors**

```bash
# Solution: Use token rotation
export GITHUB_TOKEN_2=your_backup_token
export GITHUB_TOKEN_3=your_third_token

# Or increase delay between requests
--delay 2.0
```

**Memory Issues**

```bash
# Solution: Reduce concurrent workers
concurrency:
  max_workers: 2

# Or process in smaller batches
limits:
  max_repos: 50
```

**Deduplication Database Errors**

```bash
# Solution: Reset deduplication database
rm data/dedup.db
python github_prospect_scraper.py --no-dedup
```

### Debug Mode

Enable detailed logging for troubleshooting:

```bash
python github_prospect_scraper.py --debug --verbose
```

### Performance Optimization

```bash
# Use concurrent processing
concurrency:
  enabled: true
  max_workers: 4

# Enable caching
cache_dir: ".cache"

# Optimize query specificity
query: "language:python stars:100..1000 pushed:>2024-01-01"
```

## 🧪 Testing

### Unit Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test module
python -m pytest tests/test_scraper.py -v

# Run with coverage
python -m pytest tests/ --cov=github_prospect_scraper --cov-report=html
```

### Integration Tests

```bash
# Test with real GitHub API (requires token)
python -m pytest tests/test_integration.py -v

# Test with mock data
python -m pytest tests/test_mock.py -v
```

### Load Testing

```bash
# Test concurrent processing
python load_test.py --workers 8 --repos 1000

# Test rate limiting
python rate_limit_test.py --duration 3600
```

## 📚 API Reference

### GitHubScraper Class

```python
class GitHubScraper:
    def __init__(self, token: str, config: dict, output_path: str = None, output_dir: str = None)

    def scrape(self) -> List[Prospect]:
        """Main scraping method"""

    def search_repos(self) -> List[dict]:
        """Search GitHub repositories"""

    def process_repo_concurrent(self, repo: dict) -> ProcessingResult:
        """Process repository with concurrent operations"""

    def create_prospect(self, author_data: dict, repo: dict) -> Prospect:
        """Create Prospect object from API data"""
```

### Prospect Dataclass

```python
@dataclass
class Prospect:
    # Core identification
    lead_id: str
    login: str

    # Personal info
    name: Optional[str]
    company: Optional[str]
    email_public_commit: Optional[str]

    # Repository context
    repo_full_name: str
    signal: str
    signal_type: str

    # Scoring
    prospect_score: int
    prospect_tier: str

    # Methods
    def has_email(self) -> bool
    def get_best_email(self) -> Optional[str]
    def to_dict(self) -> dict
```

## 🤝 Contributing

### Development Setup

```bash
# Fork and clone
git clone https://github.com/yourusername/leads.git
cd leads

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/
```

### Code Standards

- **Type Hints**: Full type annotation required
- **Docstrings**: Comprehensive documentation for all public methods
- **Testing**: 90%+ test coverage required
- **Linting**: Black formatting and flake8 compliance

### Pull Request Process

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Write tests for new functionality
4. Ensure all tests pass (`python -m pytest`)
5. Update documentation
6. Submit pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- GitHub API for providing comprehensive developer data
- The open source community for inspiration and contributions
- All contributors who help improve the tool

---

**Built for Lead Intelligence • Made with ❤️ by the Open Source Community**
