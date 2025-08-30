#!/usr/bin/env python3
"""
Enhanced Data Collection System for Phase 1
Implements the battle-tested plan with ICP selection, hard limits, and amazing logging
"""

import os
import json
import time
import hashlib
import sqlite3
import logging
import pathlib
from dataclasses import dataclass, field
from typing import List, Literal, Dict, Any, Optional, Iterator
from datetime import datetime, timedelta
import requests
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import yaml

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class Limits:
    """Hard limits for data collection"""
    max_repos: int
    max_leads: int
    per_repo_events: int


@dataclass
class GithubCfg:
    """GitHub API configuration"""
    per_page: int = 100
    timeout_secs: int = 15
    retries: int = 3
    backoff_base_secs: float = 2.0
    jitter: bool = True


@dataclass
class Defaults:
    """Default configuration values"""
    lookback_days: int
    global_limits: Limits
    dedupe_db: str
    out_dir: str
    log_dir: str
    github: GithubCfg


@dataclass
class AppConfig:
    """Main application configuration"""
    defaults: Defaults
    icps: Dict[str, Any]


@dataclass
class RunContext:
    """Context for a data collection run"""
    run_id: str
    started_at: datetime
    icps: List[str]
    limits: Limits
    flags: Dict[str, Any]


@dataclass
class Prospect:
    """Enhanced prospect data structure"""
    lead_id: str
    login: str
    name: Optional[str]
    repo_full_name: str
    signal_type: str
    signal: str
    signal_at: str
    stars: int
    topics: List[str]
    language: str
    github_user_url: str
    github_repo_url: str
    icp: str
    collected_at: str
    run_id: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'lead_id': self.lead_id,
            'login': self.login,
            'name': self.name,
            'repo_full_name': self.repo_full_name,
            'signal_type': self.signal_type,
            'signal': self.signal,
            'signal_at': self.signal_at,
            'stars': self.stars,
            'topics': self.topics,
            'language': self.language,
            'github_user_url': self.github_user_url,
            'github_repo_url': self.github_repo_url,
            'icp': self.icp,
            'collected_at': self.collected_at,
            'run_id': self.run_id
        }


class JsonFormatter(logging.Formatter):
    """JSON formatter for structured logging"""
    def format(self, record):
        base = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "lvl": record.levelname,
            "msg": record.getMessage(),
        }
        if hasattr(record, "ctx"):
            base.update(record.ctx)
        return json.dumps(base, ensure_ascii=False)


class Deduper:
    """SQLite-based deduplication system"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database"""
        pathlib.Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS seen_leads (
                    lead_id TEXT PRIMARY KEY,
                    first_seen_ts TEXT NOT NULL,
                    icp TEXT,
                    repo_full_name TEXT,
                    login TEXT
                )
            ''')

    def already_seen(self, lead_id: str) -> bool:
        """Check if lead_id has been seen before"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT 1 FROM seen_leads WHERE lead_id = ?',
                (lead_id,)
            )
            return cursor.fetchone() is not None

    def mark_seen(self, prospect: Prospect):
        """Mark a prospect as seen"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'INSERT OR IGNORE INTO seen_leads VALUES (?, ?, ?, ?, ?)',
                (
                    prospect.lead_id,
                    prospect.collected_at,
                    prospect.icp,
                    prospect.repo_full_name,
                    prospect.login
                )
            )


class RawWriter:
    """JSONL writer for raw prospect data"""

    def __init__(self, output_path: str):
        self.output_path = output_path
        pathlib.Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    def write(self, prospect: Prospect):
        """Write a prospect to the JSONL file"""
        with open(self.output_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(prospect.to_dict(), ensure_ascii=False) + '\n')


class QueryPlanner:
    """Plans and generates GitHub search queries for ICPs"""

    def __init__(self, config: AppConfig):
        self.config = config

    def queries_for(self, icp_key: str) -> List[str]:
        """Generate search queries for a specific ICP"""
        if icp_key not in self.config.icps:
            raise ValueError(f"Unknown ICP: {icp_key}")

        icp_config = self.config.icps[icp_key]
        if not icp_config.get('enabled', True):
            return []

        segments = icp_config['search']['segments']
        queries = []

        for segment in segments:
            # Replace {date:X} placeholders with actual dates
            query = self._expand_date_placeholders(segment)
            queries.append(query)

        return queries

    def _expand_date_placeholders(self, query: str) -> str:
        """Replace {date:X} placeholders with actual ISO dates"""
        import re

        def replace_date(match):
            days = int(match.group(1))
            cutoff_date = datetime.now() - timedelta(days=days)
            return cutoff_date.strftime('%Y-%m-%d')

        return re.sub(r'\{date:(\d+)\}', replace_date, query)


class GitHubSearchClient:
    """Enhanced GitHub API client with rate limiting and retries"""

    def __init__(self, token: str, config: GithubCfg):
        self.token = token
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'leads-intelligence/1.0'
        })

        # Rate limiting state
        self.rate_limit_remaining = 2000  # More conservative
        self.rate_limit_reset = None

    def search_repos(self, query: str) -> Iterator[Dict]:
        """Search repositories with pagination"""
        page = 1

        while True:
            params = {
                'q': query,
                'sort': 'updated',
                'order': 'desc',
                'per_page': self.config.per_page,
                'page': page
            }

            response = self._make_request('GET', '/search/repositories', params=params)
            if not response:
                break

            data = response.json()
            items = data.get('items', [])

            for item in items:
                yield item

            # Check if we have more pages
            if len(items) < self.config.per_page:
                break

            page += 1

    def fetch_signals(self, repo: Dict, per_repo_cap: int) -> Iterator[Dict]:
        """Fetch recent signals (PRs, commits, issues) for a repository"""
        owner = repo['owner']['login']
        repo_name = repo['name']

        # Fetch recent PRs
        prs = self._fetch_recent_prs(owner, repo_name, per_repo_cap)
        for pr in prs[:per_repo_cap]:
            yield {
                'type': 'pr',
                'data': pr,
                'repo': repo
            }

        # Fetch recent commits
        commits = self._fetch_recent_commits(owner, repo_name, per_repo_cap)
        for commit in commits[:per_repo_cap]:
            yield {
                'type': 'commit',
                'data': commit,
                'repo': repo
            }

        # Fetch recent issues
        issues = self._fetch_recent_issues(owner, repo_name, per_repo_cap)
        for issue in issues[:per_repo_cap]:
            yield {
                'type': 'issue',
                'data': issue,
                'repo': repo
            }

    def _fetch_recent_prs(self, owner: str, repo: str, limit: int) -> List[Dict]:
        """Fetch recent pull requests"""
        params = {
            'state': 'all',
            'sort': 'updated',
            'direction': 'desc',
            'per_page': min(limit, 100)
        }

        response = self._make_request('GET', f'/repos/{owner}/{repo}/pulls', params=params)
        if response:
            return response.json()
        return []

    def _fetch_recent_commits(self, owner: str, repo: str, limit: int) -> List[Dict]:
        """Fetch recent commits"""
        params = {
            'per_page': min(limit, 100)
        }

        response = self._make_request('GET', f'/repos/{owner}/{repo}/commits', params=params)
        if response:
            return response.json()
        return []

    def _fetch_recent_issues(self, owner: str, repo: str, limit: int) -> List[Dict]:
        """Fetch recent issues"""
        params = {
            'state': 'all',
            'sort': 'updated',
            'direction': 'desc',
            'per_page': min(limit, 100)
        }

        response = self._make_request('GET', f'/repos/{owner}/{repo}/issues', params=params)
        if response:
            # Filter out pull requests (they're included in issues)
            issues = [issue for issue in response.json() if 'pull_request' not in issue]
            return issues
        return []

    def _make_request(self, method: str, endpoint: str, **kwargs) -> Optional[requests.Response]:
        """Make a request with rate limiting and retries"""
        url = f'https://api.github.com{endpoint}'

        for attempt in range(self.config.retries):
            try:
                # Check rate limit
                if self.rate_limit_remaining <= 100:  # More conservative threshold
                    self._wait_for_rate_limit_reset()

                response = self.session.request(method, url, timeout=self.config.timeout_secs, **kwargs)

                # Update rate limit info
                if 'X-RateLimit-Remaining' in response.headers:
                    self.rate_limit_remaining = int(response.headers['X-RateLimit-Remaining'])
                if 'X-RateLimit-Reset' in response.headers:
                    self.rate_limit_reset = int(response.headers['X-RateLimit-Reset'])

                if response.status_code == 200:
                    return response
                elif response.status_code == 403:
                    # Rate limited
                    self._wait_for_rate_limit_reset()
                    continue
                elif response.status_code >= 400:
                    logger.warning(f"API error {response.status_code}: {response.text}")
                    return None

            except Exception as e:
                logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
                if attempt < self.config.retries - 1:
                    time.sleep(self.config.backoff_base_secs * (2 ** attempt))

        return None

    def _wait_for_rate_limit_reset(self):
        """Wait until rate limit resets"""
        if self.rate_limit_reset:
            reset_time = datetime.fromtimestamp(self.rate_limit_reset)
            now = datetime.now()
            wait_seconds = (reset_time - now).total_seconds()

            if wait_seconds > 0:
                logger.info(f"Rate limited. Waiting {wait_seconds:.0f} seconds until reset.")
                time.sleep(wait_seconds)


def load_config(path: str) -> AppConfig:
    """Load and validate configuration"""
    with open(path) as f:
        raw = yaml.safe_load(f)

    # Validate required fields
    if 'defaults' not in raw:
        raise ValueError("Missing 'defaults' section in config")
    if 'icps' not in raw:
        raise ValueError("Missing 'icps' section in config")

    # Extract and construct dataclasses properly
    defaults_data = raw['defaults']
    icps_data = raw['icps']

    # Construct GithubCfg
    github_data = defaults_data.get('github', {})
    github_cfg = GithubCfg(**github_data)

    # Construct Limits
    limits_data = defaults_data.get('global_limits', {})
    limits = Limits(**limits_data)

    # Construct Defaults
    defaults = Defaults(
        lookback_days=defaults_data.get('lookback_days', 30),
        global_limits=limits,
        dedupe_db=defaults_data.get('dedupe_db', 'lead_intelligence/data/dedup.sqlite3'),
        out_dir=defaults_data.get('out_dir', 'lead_intelligence/data/raw'),
        log_dir=defaults_data.get('log_dir', 'lead_intelligence/logs'),
        github=github_cfg
    )

    return AppConfig(defaults=defaults, icps=icps_data)


def setup_logging(log_dir: str, run_id: str):
    """Setup dual logging (console + JSON file)"""
    pathlib.Path(log_dir).mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # Console handler (human-readable)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("%(asctime)s %(levelname)-4s %(message)s"))
    root.addHandler(ch)

    # JSON file handler (machine-readable)
    fh = logging.FileHandler(f"{log_dir}/run_{run_id}.jsonl", encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(JsonFormatter())
    root.addHandler(fh)

    return root


def generate_run_id() -> str:
    """Generate a unique run ID"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    random_suffix = hashlib.md5(str(time.time()).encode()).hexdigest()[:6]
    return f"{timestamp}_{random_suffix}"


def assemble_prospect(signal_data: Dict, icp_key: str, run_id: str) -> Prospect:
    """Assemble a Prospect object from signal data"""
    signal_type = signal_data['type']
    data = signal_data['data']
    repo = signal_data['repo']

    # Generate lead_id
    if signal_type == 'pr':
        user_login = data.get('user', {}).get('login', 'unknown')
        lead_content = f"{user_login}:{repo.get('full_name') or 'unknown/unknown'}"
    elif signal_type == 'commit':
        user_login = data.get('author', {}).get('login') or data.get('commit', {}).get('author', {}).get('name', 'unknown')
        lead_content = f"{user_login}:{repo.get('full_name') or 'unknown/unknown'}"
    elif signal_type == 'issue':
        user_login = data.get('user', {}).get('login', 'unknown')
        lead_content = f"{user_login}:{repo.get('full_name') or 'unknown/unknown'}"
    else:
        user_login = 'unknown'
        lead_content = f"unknown:{repo['full_name']}"

    lead_id = hashlib.sha1(lead_content.encode()).hexdigest()[:12]

    # Extract signal information
    if signal_type == 'pr':
        signal = f"PR #{data.get('number', 'N/A')}: {data.get('title', 'No title')[:80]}"
        signal_at = data.get('updated_at', data.get('created_at', datetime.now().isoformat()))
    elif signal_type == 'commit':
        commit_msg = data.get('commit', {}).get('message', 'No message')
        signal = f"Commit: {commit_msg.split('\n')[0][:80]}"
        signal_at = data.get('commit', {}).get('committer', {}).get('date', datetime.now().isoformat())
    elif signal_type == 'issue':
        signal = f"Issue #{data.get('number', 'N/A')}: {data.get('title', 'No title')[:80]}"
        signal_at = data.get('updated_at', data.get('created_at', datetime.now().isoformat()))
    else:
        signal = f"Unknown signal: {signal_type}"
        signal_at = datetime.now().isoformat()

    return Prospect(
        lead_id=lead_id,
        login=user_login,
        name=data.get('user', {}).get('name') if signal_type in ['pr', 'issue'] else data.get('commit', {}).get('author', {}).get('name'),
        repo_full_name=repo.get('full_name') or 'unknown/unknown',
        signal_type=signal_type,
        signal=signal,
        signal_at=signal_at,
        stars=int(repo.get('stargazers_count', 0) or 0),
        topics=repo.get('topics', []) or [],
        language=repo.get('language', 'Unknown') or 'Unknown',
        github_user_url=f"https://github.com/{user_login}",
        github_repo_url=repo.get('html_url', ''),
        icp=icp_key,
        collected_at=datetime.now().isoformat(),
        run_id=run_id
    )


class DataCollector:
    """Main data collection orchestrator"""

    def __init__(self, config_path: str, github_token: str):
        self.config = load_config(config_path)
        self.github_token = github_token
        self.github_client = GitHubSearchClient(github_token, self.config.defaults.github)
        self.query_planner = QueryPlanner(self.config)

    def collect_for_icps(self, icp_keys: List[str], limits: Limits, run_id: str) -> Dict[str, Any]:
        """Collect data for specified ICPs with hard limits"""

        # Setup logging
        setup_logging(self.config.defaults.log_dir, run_id)

        # Initialize components
        deduper = Deduper(self.config.defaults.dedupe_db)

        # Create output file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_path = f"{self.config.defaults.out_dir}/raw_prospects_{timestamp}.jsonl"
        writer = RawWriter(output_path)

        # Counters for hard limits
        counters = {
            'repos_scanned': 0,
            'leads_emitted': 0,
            'dedup_dropped': 0
        }

        run_ctx = RunContext(
            run_id=run_id,
            started_at=datetime.now(),
            icps=icp_keys,
            limits=limits,
            flags={}
        )

        logger.info("🚀 Starting data collection", extra={
            "ctx": {
                "run_id": run_id,
                "icps": icp_keys,
                "limits": {
                    "max_repos": limits.max_repos,
                    "max_leads": limits.max_leads,
                    "per_repo_events": limits.per_repo_events
                }
            }
        })

        # Collect for each ICP
        for icp_key in icp_keys:
            logger.info(f"🎯 Collecting for ICP: {icp_key}")

            try:
                self._collect_for_icp(
                    icp_key, self.query_planner, self.github_client,
                    limits, counters, writer, deduper, run_ctx
                )
            except Exception as e:
                logger.error(f"Failed to collect for ICP {icp_key}: {e}", extra={
                    "ctx": {"icp": icp_key, "error": str(e)}
                })

        # Generate summary
        summary = {
            "run_id": run_id,
            "icps": icp_keys,
            "repos_scanned": counters["repos_scanned"],
            "leads_emitted": counters["leads_emitted"],
            "dedup_dropped": counters["dedup_dropped"],
            "output_file": output_path,
            "completed_at": datetime.now().isoformat()
        }

        # Save summary
        summary_path = f"{self.config.defaults.log_dir}/run_{run_id}_summary.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)

        logger.info("✅ Data collection complete", extra={
            "ctx": {
                "run_id": run_id,
                "repos_scanned": counters["repos_scanned"],
                "leads_emitted": counters["leads_emitted"],
                "dedup_dropped": counters["dedup_dropped"]
            }
        })

        return summary

    def _collect_for_icp(self, icp_key: str, planner: QueryPlanner, gh: GitHubSearchClient,
                        limits: Limits, counters: Dict, writer: RawWriter,
                        deduper: Deduper, run_ctx: RunContext):
        """Collect data for a single ICP with early-stop logic"""

        queries = planner.queries_for(icp_key)
        if not queries:
            logger.warning(f"No queries generated for ICP: {icp_key}")
            return

        for query in queries:
            logger.info(f"🔍 Searching with query: {query[:100]}...")

            for repo in gh.search_repos(query):
                # Check repo limit
                if counters["repos_scanned"] >= limits.max_repos:
                    logger.info("Repo cap reached", extra={
                        "ctx": {
                            "event": "early_stop",
                            "reason": "max_repos",
                            "repos_scanned": counters["repos_scanned"]
                        }
                    })
                    return

                counters["repos_scanned"] += 1

                # Fetch signals for this repo
                events_processed = 0
                for signal_data in gh.fetch_signals(repo, limits.per_repo_events):
                    # Check lead limit
                    if counters["leads_emitted"] >= limits.max_leads:
                        logger.info("Lead cap reached", extra={
                            "ctx": {
                                "event": "early_stop",
                                "reason": "max_leads",
                                "leads_emitted": counters["leads_emitted"]
                            }
                        })
                        return

                    events_processed += 1
                    if events_processed > limits.per_repo_events:
                        break

                    # Assemble prospect
                    prospect = assemble_prospect(signal_data, icp_key, run_ctx.run_id)

                    # Check deduplication
                    if deduper.already_seen(prospect.lead_id):
                        counters["dedup_dropped"] += 1
                        continue

                    # Write and mark as seen
                    writer.write(prospect)
                    deduper.mark_seen(prospect)
                    counters["leads_emitted"] += 1

                logger.info(f"📦 Processed repo {repo.get('full_name') or 'unknown/unknown'}: {events_processed} events", extra={
                    "ctx": {
                        "repo": repo.get('full_name') or 'unknown/unknown',
                        "events_processed": events_processed,
                        "leads_emitted": counters["leads_emitted"]
                    }
                })


# CLI interface
def main():
    """Main entry point for enhanced data collection"""
    import argparse

    parser = argparse.ArgumentParser(description="Enhanced Lead Intelligence Data Collector")
    parser.add_argument("--icp", nargs="+", required=True,
                       help="ICP keys to collect (comma-separated or multiple)")
    parser.add_argument("--max-repos", type=int, default=300,
                       help="Maximum repositories to scan")
    parser.add_argument("--max-leads", type=int, default=200,
                       help="Maximum leads to collect")
    parser.add_argument("--per-repo-events", type=int, default=25,
                       help="Maximum events per repository")
    parser.add_argument("--config", default="config.yaml",
                       help="Configuration file path")
    parser.add_argument("--github-token", help="GitHub token (or set GITHUB_TOKEN env var)")

    args = parser.parse_args()

    # Get GitHub token (hardcoded)
    github_token = args.github_token or "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"

    # Parse ICP keys
    icp_keys = []
    for icp_arg in args.icp:
        if "," in icp_arg:
            icp_keys.extend([k.strip() for k in icp_arg.split(",")])
        else:
            icp_keys.append(icp_arg)

    # Validate ICPs are "all" or specific keys
    if "all" in icp_keys:
        # Load all enabled ICPs from config
        config = load_config(args.config)
        icp_keys = [k for k, v in config.icps.items() if v.get('enabled', True)]

    # Setup limits
    limits = Limits(
        max_repos=args.max_repos,
        max_leads=args.max_leads,
        per_repo_events=args.per_repo_events
    )

    # Generate run ID
    run_id = generate_run_id()

    # Run collection
    collector = DataCollector(args.config, github_token)
    summary = collector.collect_for_icps(icp_keys, limits, run_id)

    print(f"\n📊 Collection Summary:")
    print(f"   Run ID: {summary['run_id']}")
    print(f"   ICPs: {', '.join(summary['icps'])}")
    print(f"   Repos scanned: {summary['repos_scanned']}")
    print(f"   Leads emitted: {summary['leads_emitted']}")
    print(f"   Dedup dropped: {summary['dedup_dropped']}")
    print(f"   Output: {summary['output_file']}")

    return 0


if __name__ == "__main__":
    exit(main())
