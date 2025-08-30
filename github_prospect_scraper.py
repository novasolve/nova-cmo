#!/usr/bin/env python3
"""
GitHub Prospect Scraper
Collects contributors from GitHub repos based on search criteria
"""

import os
import sys
import csv
import time
import json
import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Set, Any
import copy
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import yaml
import argparse
from dataclasses import dataclass, asdict
from urllib.parse import urlparse
from tqdm import tqdm
import sqlite3

# Import core modules
from lead_intelligence.core.prospect_scorer import ProspectScorer
from lead_intelligence.core.concurrent_processor import ConcurrentProcessor, ProcessingResult
from lead_intelligence.core.job_metadata import JobTracker, JobStats
from lead_intelligence.core.identity_deduper import IdentityDeduper
from lead_intelligence.core.timezone_utils import days_ago


@dataclass
class Prospect:
    """Represents a GitHub prospect/contributor with ALL available data"""
    # Core identification
    lead_id: str
    login: str
    id: Optional[int]  # GitHub user ID
    node_id: Optional[str]  # GitHub GraphQL node ID

    # Personal info
    name: Optional[str]
    company: Optional[str]
    email_public_commit: Optional[str]
    email_profile: Optional[str]  # Email from GitHub profile
    location: Optional[str]
    bio: Optional[str]
    pronouns: Optional[str]  # he/him, she/her, etc.

    # Repository context
    repo_full_name: str
    repo_description: Optional[str]
    signal: str
    signal_type: str  # 'pr', 'commit', 'core_contributor', etc.
    signal_at: str
    topics: str
    language: str
    stars: int
    forks: Optional[int]
    watchers: Optional[int]

    # Maintainer status (new fields)
    is_maintainer: bool = False
    is_org_member: bool = False
    is_codeowner: bool = False
    permission_level: str = 'read'
    commit_count_90d: Optional[int] = None

    # Contact enrichment (new fields)
    contactability_score: int = 0
    email_type: str = 'unknown'
    is_disposable_email: bool = False
    corporate_domain: Optional[str] = None
    linkedin_query: Optional[str] = None

    # Scoring and tiering (new fields)
    prospect_score: int = 0
    prospect_tier: str = 'unknown'
    scoring_components: Optional[Dict[str, int]] = None
    risk_factors: Optional[List[str]] = None
    priority_signals: Optional[List[str]] = None
    cohort: Optional[Dict[str, Any]] = None

    # Compliance (new fields)
    compliance_risk_level: str = 'unknown'
    compliance_blocked: bool = False
    compliance_risk_factors: Optional[List[str]] = None
    geo_location: Optional[str] = None
    
    # URLs
    github_user_url: Optional[str] = None
    github_repo_url: Optional[str] = None
    avatar_url: Optional[str] = None
    html_url: Optional[str] = None
    api_url: Optional[str] = None
    followers_url: Optional[str] = None
    following_url: Optional[str] = None
    gists_url: Optional[str] = None
    starred_url: Optional[str] = None
    subscriptions_url: Optional[str] = None
    organizations_url: Optional[str] = None
    repos_url: Optional[str] = None
    events_url: Optional[str] = None
    received_events_url: Optional[str] = None

    # Social/Professional
    twitter_username: Optional[str] = None
    blog: Optional[str] = None
    linkedin_username: Optional[str] = None  # Extracted from blog if linkedin URL
    hireable: Optional[bool] = None

    # GitHub Statistics
    public_repos: Optional[int] = None
    public_gists: Optional[int] = None
    followers: Optional[int] = None
    following: Optional[int] = None
    total_private_repos: Optional[int] = None
    owned_private_repos: Optional[int] = None
    private_gists: Optional[int] = None
    disk_usage: Optional[int] = None
    collaborators: Optional[int] = None

    # Contribution data (requires additional API calls)
    contributions_last_year: Optional[int] = None
    total_contributions: Optional[int] = None
    longest_streak: Optional[int] = None
    current_streak: Optional[int] = None

    # Account metadata
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    type: Optional[str] = None  # User type
    site_admin: Optional[bool] = None
    gravatar_id: Optional[str] = None
    suspended_at: Optional[str] = None

    # Plan information
    plan_name: Optional[str] = None
    plan_space: Optional[int] = None
    plan_collaborators: Optional[int] = None
    plan_private_repos: Optional[int] = None
    
    # Additional flags
    two_factor_authentication: Optional[bool] = None
    has_organization_projects: Optional[bool] = None
    has_repository_projects: Optional[bool] = None
    
    def has_email(self) -> bool:
        """Check if prospect has any email"""
        return bool(self.email_public_commit or self.email_profile)
    
    def get_best_email(self) -> Optional[str]:
        """Get the best available email"""
        # Prefer profile email as it's explicitly public
        return self.email_profile or self.email_public_commit
    
    def get_linkedin(self) -> Optional[str]:
        """Extract LinkedIn from blog URL if present"""
        if self.blog and 'linkedin.com/in/' in self.blog:
            return self.blog
        return self.linkedin_username
    
    def to_dict(self):
        return asdict(self)


class TimeoutSession(requests.Session):
    """requests.Session that applies a default timeout to all requests unless provided."""
    def __init__(self, default_timeout_seconds: int):
        super().__init__()
        self._default_timeout_seconds = default_timeout_seconds

    def request(self, *args, **kwargs):  # type: ignore[override]
        kwargs.setdefault('timeout', self._default_timeout_seconds)
        return super().request(*args, **kwargs)


class GitHubScraper:
    """Scrapes GitHub for prospect data"""
    
    def __init__(self, token: str, config: dict, output_path: str = None, output_dir: Optional[str] = None, icp_config_path: Optional[str] = None):
        self.token = token
        self.config = config
        self.output_path = output_path
        self.output_dir = output_dir
        
        # Initialize token rotation support
        self.tokens = [token] if token else []
        self.current_token_index = 0
        
        # Add backup tokens from environment
        for i in range(2, 10):
            backup_token = os.environ.get(f'GITHUB_TOKEN_{i}')
            if backup_token and backup_token not in self.tokens:
                self.tokens.append(backup_token)
        
        if len(self.tokens) > 1:
            print(f"🔑 Token rotation enabled with {len(self.tokens)} tokens")

        # Load ICP configuration if provided
        self.icp_config = {}
        if icp_config_path:
            try:
                with open(icp_config_path, 'r') as f:
                    self.icp_config = yaml.safe_load(f) or {}
                # Add ICP config to main config for backward compatibility
                self.config['icp'] = self.icp_config
            except Exception as e:
                print(f"⚠️  Failed to load ICP config from {icp_config_path}: {e}")
                print("Continuing without ICP filters...")

        # HTTP timeout (secs)
        try:
            self.timeout_secs = int(((self.config.get('http') or {}).get('timeout_secs')) or 15)
        except Exception:
            self.timeout_secs = 15
        self.session = self._create_session(self.timeout_secs)
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'leads-scraper/1.0'
        }
        # Only add auth header if token is provided and valid
        if token and token.strip():
            self.headers['Authorization'] = self._get_auth_header(token)
        self.prospects: Set[str] = set()  # Track unique lead_ids
        self.all_prospects: List[Prospect] = []
        self.csv_file = None
        self.csv_writer = None
        self.csv_initialized = False
        # Counter for prospects that have an email (used for lead limits/progress)
        self.leads_with_email_count = 0
        # Accumulators for Attio-style exports
        self.people_records: Dict[str, Dict] = {}
        self.repo_records: Dict[str, Dict] = {}
        self.membership_records: Dict[str, Dict] = {}
        self.signal_records: Dict[str, Dict] = {}
        self.repo_details_cache: Dict[str, Dict] = {}
        # Caches
        self.user_cache: Dict[str, Dict] = {}
        self.contrib_cache: Dict[str, Dict] = {}
        self.org_cache: Dict[str, Dict] = {}
        # Initialize ProspectScorer
        self.prospect_scorer = ProspectScorer(icp_config_path)

        # Initialize ConcurrentProcessor
        concurrency_config = self.config.get('concurrency', {})
        self.concurrent_processor = ConcurrentProcessor(
            max_workers=concurrency_config.get('max_workers', 4),
            requests_per_hour=concurrency_config.get('requests_per_hour', 5000),
            cache_dir=concurrency_config.get('cache_dir', '.cache')
        )

        # Initialize JobTracker
        self.job_tracker = JobTracker(self.output_dir or "lead_intelligence/data")

        # Initialize IdentityDeduper
        self.identity_deduper = IdentityDeduper()

        # Dedup configuration
        dedup_cfg = (self.config.get('dedup') or {}) if isinstance(self.config, dict) else {}
        self.dedup_enabled: bool = bool(dedup_cfg.get('enabled', True))
        self.dedup_db_path: str = dedup_cfg.get('db_path') or 'data/dedup.db'
        self._dedup_conn: Optional[sqlite3.Connection] = None
        if self.dedup_enabled:
            try:
                os.makedirs(os.path.dirname(self.dedup_db_path) or '.', exist_ok=True)
                self._dedup_conn = sqlite3.connect(self.dedup_db_path)
                cur = self._dedup_conn.cursor()
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS seen_people (login TEXT PRIMARY KEY, first_seen TEXT NOT NULL)"
                )
                self._dedup_conn.commit()
            except Exception as e:
                print(f"⚠️  Dedup DB init failed at {self.dedup_db_path}: {e}. Continuing without dedup.")
                self.dedup_enabled = False
                self._dedup_conn = None

    def _get_auth_header(self, token: str) -> str:
        """Get the appropriate authorization header based on token format"""
        if not token:
            return ""
        token = token.strip()

        # Detect token type and use appropriate authorization method
        if token.startswith('ghp_'):
            # Classic personal access token - use token auth
            return f'token {token}'
        elif token.startswith('github_token_'):
            # Fine-grained personal access token - use Bearer auth
            return f'Bearer {token}'
        elif token.startswith('ghs_'):
            # GitHub App installation access token - use token auth
            return f'token {token}'
        else:
            # For unknown formats, default to token auth (more compatible)
            # This handles both old-style tokens and new formats
            return f'token {token}'

    def _dedup_seen(self, login: Optional[str]) -> bool:
        if not (self.dedup_enabled and self._dedup_conn and login):
            return False
        try:
            cur = self._dedup_conn.cursor()
            cur.execute("SELECT 1 FROM seen_people WHERE login = ?", (login,))
            return cur.fetchone() is not None
        except Exception:
            return False

    def _dedup_mark(self, login: Optional[str]):
        if not (self.dedup_enabled and self._dedup_conn and login):
            return
        try:
            cur = self._dedup_conn.cursor()
            cur.execute(
                "INSERT OR IGNORE INTO seen_people(login, first_seen) VALUES(?, ?)",
                (login, to_utc_iso8601(utc_now()))
            )
            self._dedup_conn.commit()
        except Exception:
            pass
        
    def _create_session(self, timeout_secs: int):
        """Create session with retry logic and default timeout"""
        session = TimeoutSession(timeout_secs)
        retry = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session
        
    def _render_query(self, raw_query: str) -> str:
        """Render dynamic placeholders in the search query.

        Supported placeholders:
        - {date:N} → replaced with YYYY-MM-DD for (today - N days)
        """
        q = str(raw_query or '')
        # {date:N} → YYYY-MM-DD (UTC today minus N days)
        def _date_repl(match: re.Match) -> str:
            try:
                days_back = int(match.group(1))
            except Exception:
                days_back = 0
            target = datetime.now(timezone.utc) - timedelta(days=days_back)
            return target.strftime('%Y-%m-%d')
        q = re.sub(r"\{date:(\d+)\}", _date_repl, q)
        # Normalize whitespace
        q = ' '.join(q.split())
        return q
        
    def _rate_limit_wait(self, response):
        """Handle GitHub rate limiting"""
        # Check remaining requests before we hit the limit
        remaining = response.headers.get('X-RateLimit-Remaining', '0')
        limit = response.headers.get('X-RateLimit-Limit', '5000')
        reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
        
        # Log current rate limit status
        if remaining and int(remaining) < 100:
            current_time = time.time()
            minutes_until_reset = max(0, (reset_time - current_time) / 60)
            print(f"⚠️  GitHub API rate limit: {remaining}/{limit} remaining. Resets in {minutes_until_reset:.1f} minutes")
        
        if response.status_code == 403:
            # Check if it's rate limiting or other 403 error
            if 'rate limit' in response.text.lower() or reset_time:
                wait_time = reset_time - int(time.time()) + 5
                if wait_time > 0:
                    print(f"🚫 GitHub rate limit exceeded! Token: {self.token[:20]}...")
                    print(f"   Would need to wait {wait_time} seconds ({wait_time/60:.1f} minutes)")
                    
                    # Try rotating to a backup token
                    if self._try_rotate_token():
                        return True  # Successfully rotated, retry the request
                    
                    # No backup tokens available, wait
                    print(f"⏱️  No backup tokens available. Waiting {wait_time/60:.1f} minutes...")
                    time.sleep(wait_time)
                    return True
        return False
    
    def check_rate_limit(self):
        """Check current GitHub API rate limit status"""
        url = "https://api.github.com/rate_limit"
        response = self.session.get(url, headers=self.headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            core = data.get('resources', {}).get('core', {})
            search = data.get('resources', {}).get('search', {})
            
            print("\n📊 GitHub API Rate Limit Status:")
            print(f"   Core API: {core.get('remaining', 0)}/{core.get('limit', 5000)} remaining")
            print(f"   Search API: {search.get('remaining', 0)}/{search.get('limit', 30)} remaining")
            
            # Check if we're close to limits
            if core.get('remaining', 0) < 100:
                reset_time = core.get('reset', 0)
                current_time = time.time()
                minutes_until_reset = max(0, (reset_time - current_time) / 60)
                print(f"   ⚠️  Warning: Low on API calls! Resets in {minutes_until_reset:.1f} minutes")
                
            return core.get('remaining', 0), search.get('remaining', 0)
        return None, None
    
    def _try_rotate_token(self) -> bool:
        """Try to rotate to a backup token with available rate limit"""
        if len(self.tokens) <= 1:
            return False
        
        print("🔄 Attempting to rotate to backup token...")
        
        # Try each token
        for i, token in enumerate(self.tokens):
            if token == self.token:
                continue  # Skip current token
            
            # Test the token's rate limit
            test_headers = self._get_headers(token)
            test_resp = self.session.get('https://api.github.com/rate_limit', headers=test_headers, timeout=10)
            
            if test_resp.status_code == 200:
                data = test_resp.json()
                core_remaining = data.get('resources', {}).get('core', {}).get('remaining', 0)
                
                if core_remaining > 100:  # Need at least 100 calls
                    print(f"✅ Switching to backup token {i+1} with {core_remaining} API calls remaining")
                    self.token = token
                    self.headers = test_headers
                    return True
                else:
                    print(f"   Token {i+1}: Only {core_remaining} calls remaining (need >100)")
        
        print("❌ No backup tokens have sufficient rate limit available")
        return False

    def _normalize_domain(self, value: Optional[str]) -> Optional[str]:
        """Extract and normalize a domain from an email or URL string."""
        if not value:
            return None
        s = (value or '').strip().lower()
        if '@' in s and ' ' not in s:
            domain = s.split('@', 1)[-1]
        else:
            if not s.startswith('http'):
                s = f"https://{s}"
            try:
                parsed = urlparse(s)
                domain = parsed.netloc or (parsed.path.split('/')[0] if parsed.path else '')
            except Exception:
                domain = s
        domain = domain.split(':')[0]
        if domain.startswith('www.'):
            domain = domain[4:]
        if '.' not in domain:
            return None
        return domain

    def _is_public_email_domain(self, domain: Optional[str]) -> bool:
        """Return True if the domain looks like a public/free email provider."""
        if not domain:
            return False
        domain = domain.lower()
        public_set = {
            'gmail.com', 'googlemail.com', 'outlook.com', 'hotmail.com', 'live.com', 'msn.com',
            'icloud.com', 'me.com', 'mac.com', 'aol.com', 'proton.me', 'protonmail.com', 'pm.me',
            'gmx.com', 'fastmail.com', 'tutanota.com', 'hey.com', 'hushmail.com', 'mail.com',
            'yandex.ru', 'yandex.com', 'zoho.com'
        }
        if domain in public_set:
            return True
        # Common family patterns
        if domain.startswith('yahoo.') or domain.endswith('.yahoo.com'):
            return True
        if domain.startswith('hotmail.') or domain.endswith('.hotmail.com'):
            return True
        if domain.startswith('outlook.') or domain.endswith('.outlook.com'):
            return True
        if domain.startswith('live.') or domain.endswith('.live.com'):
            return True
        return False

    def _extract_corporate_domain(self, email: Optional[str], blog_url: Optional[str], company: Optional[str]) -> Optional[str]:
        """Extract corporate domain from email, blog URL, or company name."""
        # Try email first (most reliable)
        if email and '@' in email:
            domain = email.split('@')[1].lower()
            if not self._is_public_email_domain(domain):
                return domain

        # Try blog URL
        if blog_url:
            domain = self._normalize_domain(blog_url)
            if domain and not self._is_public_email_domain(domain):
                return domain

        # Try to extract from company name (last resort)
        if company and isinstance(company, str):
            company = company.strip().lower()
            # Remove common prefixes/suffixes
            company = re.sub(r'^(the\s+|\s+inc\.?$|\s+llc\.?$|\s+corp\.?$|\s+ltd\.?$)', '', company)
            # Try to create a domain-like string
            if company and len(company.split()) == 1:
                return f"{company}.com"

        return None

    def _determine_email_type(self, email: str) -> str:
        """Determine if email is work, personal, or unknown."""
        if not email or '@' not in email:
            return 'unknown'

        domain = email.split('@')[1].lower()

        # Check if it's a public email provider
        if self._is_public_email_domain(domain):
            return 'personal'

        # Check for common work email patterns
        work_indicators = ['.com', '.org', '.net', '.io', '.dev', '.co']
        if any(indicator in domain for indicator in work_indicators):
            return 'work'

        return 'unknown'

    def _is_disposable_email(self, email: str) -> bool:
        """Check if email is from a disposable/temporary email service."""
        if not email or '@' not in email:
            return False

        domain = email.split('@')[1].lower()

        # Common disposable email domains
        disposable_domains = {
            '10minutemail.com', 'guerrillamail.com', 'mailinator.com', 'temp-mail.org',
            'throwaway.email', 'yopmail.com', 'maildrop.cc', 'tempail.com', 'mohmal.com',
            'getnada.com', 'mailcatch.com', 'fakeinbox.com', 'mail-temporaire.fr'
        }

        return domain in disposable_domains

    def _choose_main_email(self, email_profile: Optional[str], email_public_commit: Optional[str]) -> Optional[str]:
        """Select a main email preferring work domains over personal.

        Order:
        1) Non-public-domain email among [profile, commit]
        2) profile email
        3) commit email
        """
        candidates = []
        for e in [(email_profile or '').strip(), (email_public_commit or '').strip()]:
            if e and '@' in e:
                candidates.append(e)

        # Prefer non-public domains
        for e in candidates:
            dom = self._normalize_domain(e)
            if dom and not self._is_public_email_domain(dom):
                return e

        # Fallbacks
        return candidates[0] if candidates else None

    def _get_org_details(self, org_login: str) -> Dict:
        if not org_login:
            return {}
        if org_login in self.org_cache:
            return self.org_cache[org_login]
        url = f"https://api.github.com/orgs/{org_login}"
        resp = self.session.get(url, headers=self.headers, timeout=10)
        if self._rate_limit_wait(resp):
            resp = self.session.get(url, headers=self.headers, timeout=10)
        details = resp.json() if resp.status_code == 200 else {}
        self.org_cache[org_login] = details
        return details
    
    def _init_csv_file(self):
        """Initialize CSV file for incremental writing"""
        if self.output_path and not self.csv_initialized:
            self.csv_file = open(self.output_path, 'w', newline='', encoding='utf-8')
            # Define all fieldnames from Prospect dataclass
            fieldnames = [
                # Core identification
                'lead_id', 'login', 'id', 'node_id',
                # Personal info
                'name', 'company', 'email_public_commit', 'email_profile',
                'location', 'bio', 'pronouns',
                # Repository context
                'repo_full_name', 'repo_description', 'signal', 'signal_type',
                'signal_at', 'topics', 'language', 'stars', 'forks', 'watchers',
                # Maintainer status
                'is_maintainer', 'is_org_member', 'is_codeowner', 'permission_level', 'commit_count_90d',
                # Contact enrichment
                'contactability_score', 'email_type', 'is_disposable_email', 'corporate_domain', 'linkedin_query',
                # URLs
                'github_user_url', 'github_repo_url', 'avatar_url', 'html_url',
                'api_url', 'followers_url', 'following_url', 'gists_url',
                'starred_url', 'subscriptions_url', 'organizations_url',
                'repos_url', 'events_url', 'received_events_url',
                # Social/Professional
                'twitter_username', 'blog', 'linkedin_username', 'hireable',
                # GitHub Statistics
                'public_repos', 'public_gists', 'followers', 'following',
                'total_private_repos', 'owned_private_repos', 'private_gists',
                'disk_usage', 'collaborators',
                # Contribution data
                'contributions_last_year', 'total_contributions',
                'longest_streak', 'current_streak',
                # Account metadata
                'created_at', 'updated_at', 'type', 'site_admin',
                'gravatar_id', 'suspended_at',
                # Plan information
                'plan_name', 'plan_space', 'plan_collaborators', 'plan_private_repos',
                # Scoring and tiering
                'prospect_score', 'prospect_tier', 'scoring_components', 'risk_factors', 'priority_signals', 'cohort',
                # Compliance
                'compliance_risk_level', 'compliance_blocked', 'compliance_risk_factors', 'geo_location',
                # Additional flags
                'two_factor_authentication', 'has_organization_projects',
                'has_repository_projects'
            ]
            self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=fieldnames)
            self.csv_writer.writeheader()
            self.csv_file.flush()
            self.csv_initialized = True
    
    def _write_prospect_to_csv(self, prospect: Prospect):
        """Write a single prospect to CSV file immediately"""
        if self.csv_writer:
            self.csv_writer.writerow(prospect.to_dict())
            self.csv_file.flush()  # Ensure data is written immediately
    
    def _close_csv_file(self):
        """Close CSV file"""
        if self.csv_file:
            self.csv_file.close()
            self.csv_file = None
            self.csv_writer = None
        # Close dedup DB
        if self._dedup_conn:
            try:
                self._dedup_conn.close()
            except Exception:
                pass
            self._dedup_conn = None
        
    def _build_icp_query(self) -> str:
        """Build GitHub search query incorporating ICP filters"""
        base_query = self.config['search']['query']

        # Add ICP-specific filters if available
        icp_config = self.config.get('icp', {})

        # Include topics
        if icp_config.get('include_topics'):
            topic_filters = ' OR '.join([f'topic:{topic}' for topic in icp_config['include_topics']])
            base_query += f' ({topic_filters})'

        # Language filters
        if icp_config.get('languages'):
            lang_filters = ' OR '.join([f'language:{lang}' for lang in icp_config['languages']])
            base_query += f' ({lang_filters})'

        # Stars filter
        min_stars = icp_config.get('min_stars')
        if min_stars:
            if isinstance(min_stars, str):
                min_stars = int(min_stars)
            base_query += f' stars:>={min_stars}'

        # Window filter (recent activity)
        window_days = icp_config.get('window_days')
        if window_days:
            if isinstance(window_days, str):
                window_days = int(window_days)
            from datetime import datetime, timedelta
            cutoff_date = (datetime.now() - timedelta(days=window_days)).strftime('%Y-%m-%d')
            base_query += f' pushed:>={cutoff_date}'

        # Exclude archived repos
        base_query += ' archived:false fork:false'

        # Exclude common off-ICP topics
        if icp_config.get('exclude_topics'):
            exclude_filters = ' '.join([f'-topic:{topic}' for topic in icp_config['exclude_topics']])
            base_query += f' {exclude_filters}'

        # Exclude common off-ICP repo name patterns (disabled for broader search)
        # exclude_patterns = [
        #     'vpn', 'v2ray', 'warp', 'instagram', 'weibo', 'ctf', 'chromego',
        #     'hiddify', 'awesome', 'tutorial', 'examples', 'docs', 'template',
        #     'starter', 'playground', 'course', 'book', 'sample', 'dotfiles'
        # ]
        # name_excludes = ' '.join([f'-in:name {pattern}' for pattern in exclude_patterns])
        # base_query += f' {name_excludes}'

        # Prefer organizations over users if configured
        # Note: GitHub search doesn't have direct org vs user filtering
        # We'll handle this in post-processing instead

        return base_query

    def search_repos(self) -> List[Dict]:
        """Search GitHub repos based on config criteria with ICP filtering"""
        repos = []

        # Build query with ICP filters
        query = self._build_icp_query()
        sort = self.config['search'].get('sort', 'updated')
        order = self.config['search'].get('order', 'desc')
        per_page = min(self.config['search'].get('per_page', 30), 100)
        max_repos = self.config['limits']['max_repos']

        page = 1
        est_pages = max(1, (max_repos + per_page - 1) // per_page)
        pages_pbar = tqdm(total=est_pages, desc="Searching repos", unit="page", leave=False)
        while len(repos) < max_repos:
            url = f"https://api.github.com/search/repositories"
            params = {
                'q': query,
                'sort': sort,
                'order': order,
                'per_page': per_page,
                'page': page
            }

            timeout_secs = int(os.environ.get('HTTP_TIMEOUT_SECS', '10') or '10')
            response = self.session.get(url, headers=self.headers, params=params, timeout=timeout_secs)

            if self._rate_limit_wait(response):
                continue

            if response.status_code != 200:
                try:
                    err = response.json()
                except Exception:
                    err = {}
                message = (err.get('message') or '')
                # Include details when available to aid debugging (e.g., 422 Validation Failed)
                details = ''
                try:
                    if isinstance(err, dict) and err.get('errors'):
                        details = f" details={json.dumps(err.get('errors'), ensure_ascii=False)}"
                except Exception:
                    details = ''
                bad_q = params.get('q')
                tqdm.write(f"❌ Error searching repos: {response.status_code} {message}{details} q=\"{bad_q}\"")
                # Fallback: if 422 (Validation Failed), try to rewrite OR groups safely
                if response.status_code == 422 and 'q' in params and params['q']:
                    original_q = params['q']
                    attempted_queries = []
                    # 1) Try replacing each parenthesized (A OR B) group with each option individually
                    try:
                        groups = re.findall(r"\(([^)]+)\)", original_q)
                        tried_success = False
                        for g in groups:
                            if ' OR ' not in g:
                                continue
                            options = [opt.strip() for opt in g.split(' OR ') if opt.strip()]
                            for opt in options:
                                trial_q = original_q.replace(f"({g})", opt)
                                attempted_queries.append(trial_q)
                                trial_params = dict(params)
                                trial_params['q'] = trial_q
                                trial_resp = self.session.get(url, headers=self.headers, params=trial_params, timeout=timeout_secs)
                                if self._rate_limit_wait(trial_resp):
                                    trial_resp = self.session.get(url, headers=self.headers, params=trial_params, timeout=timeout_secs)
                                if trial_resp.status_code == 200:
                                    data = trial_resp.json() or {}
                                    items = data.get('items', []) or []
                                    repos.extend(items)
                                    pages_pbar.update(1)
                                    # Lock in working query for subsequent pages
                                    params['q'] = trial_q
                                    if len(items) < per_page:
                                        tried_success = True
                                        break
                                    page += 1
                                    time.sleep(self.config.get('delay', 1))
                                    tried_success = True
                                    break
                            if tried_success:
                                break
                        if tried_success:
                            continue
                    except Exception:
                        pass
                    # 2) AND fallback: replace OR with space (GitHub search defaults to AND)
                    if ' OR ' in original_q:
                        and_q = original_q.replace(' OR ', ' ')
                        attempted_queries.append(and_q)
                        trial_params = dict(params)
                        trial_params['q'] = and_q
                        trial_resp = self.session.get(url, headers=self.headers, params=trial_params, timeout=timeout_secs)
                        if self._rate_limit_wait(trial_resp):
                            trial_resp = self.session.get(url, headers=self.headers, params=trial_params, timeout=timeout_secs)
                        if trial_resp.status_code == 200:
                            data = trial_resp.json() or {}
                            items = data.get('items', []) or []
                            repos.extend(items)
                            pages_pbar.update(1)
                            params['q'] = and_q
                            if len(items) < per_page:
                                break
                            page += 1
                            time.sleep(self.config.get('delay', 1))
                            continue
                    # If we exhausted fallbacks
                    tqdm.write(f"⚠️  422 persisted after trying {len(attempted_queries)} rewritten queries")
                break

            data = response.json() or {}
            items = data.get('items', []) or []

            # Apply ICP-based filtering on results
            filtered_items = self._filter_repos_by_icp(items)
            repos.extend(filtered_items)

            pages_pbar.update(1)
            pages_pbar.set_postfix_str(f"fetched={len(repos)}")

            if len(data.get('items', [])) < per_page:
                break

            page += 1
            time.sleep(self.config.get('delay', 1))  # Be nice to GitHub

        pages_pbar.close()
        return repos[:max_repos]

    def _filter_repos_by_icp(self, repos: List[Dict]) -> List[Dict]:
        """Apply ICP-based filtering to repository results"""
        filtered = []
        icp_config = self.config.get('icp', {})

        for repo in repos:
            # Skip if doesn't match ICP criteria
            if not self._passes_icp_filters(repo, icp_config):
                continue

            filtered.append(repo)

        return filtered

    def _passes_icp_filters(self, repo: Dict, icp_config: Dict) -> bool:
        """Check if repository passes ICP filters"""
        # Check stars threshold
        min_stars = icp_config.get('min_stars')
        if min_stars and isinstance(min_stars, str):
            min_stars = int(min_stars)
        if min_stars:
            stars_count = repo.get('stargazers_count', 0)
            if stars_count is None:
                stars_count = 0
            elif isinstance(stars_count, str):
                stars_count = int(stars_count) if stars_count.isdigit() else 0
            if stars_count < min_stars:
                return False

        # Check if archived
        archived = repo.get('archived', False)
        if isinstance(archived, str):
            archived = archived.lower() in ('true', '1', 'yes')
        if archived:
            return False

        # Check if fork (unless explicitly allowed)
        fork = repo.get('fork', False)
        if isinstance(fork, str):
            fork = fork.lower() in ('true', '1', 'yes')
        include_forks = icp_config.get('include_forks', False)
        if isinstance(include_forks, str):
            include_forks = include_forks.lower() in ('true', '1', 'yes')
        if fork and not include_forks:
            return False

        # Check topics against exclude list
        topics = repo.get('topics', [])
        exclude_topics = icp_config.get('exclude_topics', [])
        if any(topic in exclude_topics for topic in topics):
            return False

        # Check repo name against exclude patterns (disabled for broader search)
        # name = repo.get('name', '').lower()
        # exclude_patterns = ['vpn', 'v2ray', 'warp', 'instagram', 'weibo', 'ctf']
        # if any(pattern in name for pattern in exclude_patterns):
        #     return False

        # Check owner type preference
        if icp_config.get('prefer_orgs'):
            owner = repo.get('owner', {})
            if owner.get('type') != 'Organization':
                # Allow some user-owned repos if they're high-quality
                stars_count = repo.get('stargazers_count', 0)
                if stars_count is None:
                    stars_count = 0
                elif isinstance(stars_count, str):
                    stars_count = int(stars_count) if stars_count.isdigit() else 0
                if stars_count < 500:
                    return False

        return True
        
    def get_pr_authors(self, repo: Dict) -> List[Dict]:
        """Get recent PR authors for a repo"""
        pr_authors = []
        if not repo or 'owner' not in repo or 'name' not in repo:
            return pr_authors
        owner = repo.get('owner', {}).get('login', '')
        repo_name = repo.get('name', '')
        if not owner or not repo_name:
            return pr_authors
        
        # Calculate date range
        days_back = self.config['filters'].get('activity_days', 90)
        since = (datetime.now() - timedelta(days=days_back)).isoformat()
        
        url = f"https://api.github.com/repos/{owner}/{repo_name}/pulls"
        params = {
            'state': 'all',
            'sort': 'updated',
            'direction': 'desc',
            'per_page': min(self.config['limits']['per_repo_prs'], 100)
        }
        
        response = self.session.get(url, headers=self.headers, params=params, timeout=10)
        
        if self._rate_limit_wait(response):
            response = self.session.get(url, headers=self.headers, params=params, timeout=10)
            
        if response.status_code == 200:
            prs = response.json()
            for pr in prs:
                if pr['user'] and pr['user']['type'] == 'User':
                    # Check if PR is within date range
                    pr_date = datetime.fromisoformat(pr['updated_at'].replace('Z', '+00:00'))
                    since_date = datetime.fromisoformat(since).replace(tzinfo=pr_date.tzinfo)
                    if pr_date > since_date:
                        pr_authors.append({
                            'user': pr['user'],
                            'signal': f"opened PR #{pr['number']}: {pr['title'][:50]}",
                            'signal_type': 'pr',
                            'signal_at': pr['updated_at'],
                            'url': pr.get('html_url')
                        })
                        
        return pr_authors
        
    def get_commit_authors(self, repo: Dict) -> List[Dict]:
        """Get recent commit authors for a repo"""
        commit_authors = []
        if not repo or 'owner' not in repo or 'name' not in repo:
            return commit_authors
        owner = repo.get('owner', {}).get('login', '')
        repo_name = repo.get('name', '')
        if not owner or not repo_name:
            return commit_authors

        # Calculate date range
        days_back = self.config['filters'].get('activity_days', 90)
        since = days_ago(days_back)
        
        url = f"https://api.github.com/repos/{owner}/{repo_name}/commits"
        params = {
            'since': since,
            'per_page': min(self.config['limits']['per_repo_commits'], 100)
        }
        
        response = self.session.get(url, headers=self.headers, params=params, timeout=10)
        
        if self._rate_limit_wait(response):
            response = self.session.get(url, headers=self.headers, params=params, timeout=10)
            
        if response.status_code == 200:
            commits = response.json()
            for commit in commits:
                if commit.get('author') and commit['author']['type'] == 'User':
                    author_data = {
                        'user': commit['author'],
                        'signal': f"committed: {commit['commit']['message'][:50]}",
                        'signal_type': 'commit',
                        'signal_at': commit['commit']['author']['date'],
                        'url': commit.get('html_url') or f"https://github.com/{owner}/{repo_name}/commit/{commit.get('sha','')}"
                    }
                    
                    # Try to get email from commit
                    if 'email' in commit['commit']['author']:
                        email = commit['commit']['author']['email']
                        if '@' in email and not email.endswith('@users.noreply.github.com'):
                            if author_data:
                                author_data['email'] = email
                            
                    commit_authors.append(author_data)
                    
        return commit_authors
        
    def get_user_details(self, username: str) -> Dict:
        """Get detailed user information"""
        url = f"https://api.github.com/users/{username}"
        response = self.session.get(url, headers=self.headers, timeout=10)
        
        if self._rate_limit_wait(response):
            response = self.session.get(url, headers=self.headers, timeout=10)
            
        if response.status_code == 200:
            return response.json()
        return {}
    
    def get_user_contributions(self, username: str) -> Dict:
        """Get user contribution statistics for the last year using GitHub GraphQL API.
        Returns a dict including contributions_last_year and per-type totals. Cached per login.
        """
        if username in self.contrib_cache:
            return self.contrib_cache[username]
        if not (self.token and self.token.strip()):
            return {}
        to_dt = datetime.now(datetime.UTC)
        from_dt = to_dt - timedelta(days=365)
        query = (
            "query($user: String!, $from: DateTime!, $to: DateTime!) {\n"
            "  user(login: $user) {\n"
            "    contributionsCollection(from: $from, to: $to) {\n"
            "      totalCommitContributions\n"
            "      totalIssueContributions\n"
            "      totalPullRequestContributions\n"
            "      totalPullRequestReviewContributions\n"
            "    }\n"
            "  }\n"
            "}"
        )
        variables = {
            "user": username,
            "from": from_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "to": to_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        headers = {
            "Authorization": self._get_auth_header(self.token),
            "Accept": "application/json",
            "User-Agent": "github-prospect-scraper/1.1"
        }
        try:
            resp = requests.post("https://api.github.com/graphql", json={"query": query, "variables": variables}, headers=headers, timeout=self.timeout_secs)
            if resp.status_code != 200:
                self.contrib_cache[username] = {}
                return {}
            data = resp.json().get("data", {})
            coll = ((data.get("user") or {}).get("contributionsCollection") or {})
            totals = {
                "totalCommitContributions": coll.get("totalCommitContributions", 0),
                "totalIssueContributions": coll.get("totalIssueContributions", 0),
                "totalPullRequestContributions": coll.get("totalPullRequestContributions", 0),
                "totalPullRequestReviewContributions": coll.get("totalPullRequestReviewContributions", 0),
            }
            contributions_last_year = sum(totals.values())
            result = {
                "contributions_last_year": contributions_last_year,
                "total_contributions": contributions_last_year,
                "longest_streak": None,
                "current_streak": None,
            }
            self.contrib_cache[username] = result
            return result
        except Exception:
            self.contrib_cache[username] = {}
            return {}

    def check_maintainer_status(self, repo_full_name: str, username: str) -> Dict[str, bool]:
        """Check if user is a maintainer/collaborator with permissions on the repo"""
        result = {
            'is_maintainer': False,
            'is_org_member': False,
            'permission_level': 'read',
            'is_codeowner': False
        }

        if not (self.token and self.token.strip()):
            return result

        try:
            # Check collaborator permissions
            collab_url = f"https://api.github.com/repos/{repo_full_name}/collaborators/{username}/permission"
            response = self.session.get(collab_url, headers=self.headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                permission = data.get('permission', 'read')
                result['permission_level'] = permission
                result['is_maintainer'] = permission in ['admin', 'maintain', 'write']

            # Check CODEOWNERS file
            result['is_codeowner'] = self._check_codeowners(repo_full_name, username)

            # Check organization membership
            owner_org = repo_full_name.split('/')[0]
            result['is_org_member'] = self._check_org_membership(owner_org, username)

        except Exception as e:
            # Silently handle permission errors (user might not have access)
            pass

        return result

    def _check_codeowners(self, repo_full_name: str, username: str) -> bool:
        """Check if user is listed in CODEOWNERS file"""
        try:
            # Try common CODEOWNERS file locations
            codeowners_paths = ['CODEOWNERS', '.github/CODEOWNERS', 'docs/CODEOWNERS']

            for path in codeowners_paths:
                url = f"https://api.github.com/repos/{repo_full_name}/contents/{path}"
                response = self.session.get(url, headers=self.headers, timeout=10)

                if response.status_code == 200:
                    import base64
                    data = response.json()
                    content = base64.b64decode(data['content']).decode('utf-8')

                    # Parse CODEOWNERS format
                    for line in content.split('\n'):
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # Remove comments from line
                            line = line.split('#')[0].strip()
                            if line:
                                parts = line.split()
                                if parts:
                                    pattern = parts[0]
                                    owners = parts[1:]
                                    if username in owners or f'@{username}' in owners:
                                        return True
        except Exception:
            pass

        return False

    def _check_org_membership(self, org_name: str, username: str) -> bool:
        """Check if user is a member of the organization"""
        try:
            # Check if org_name looks like an organization (not a user)
            org_url = f"https://api.github.com/orgs/{org_name}"
            org_response = self.session.get(org_url, headers=self.headers, timeout=10)

            if org_response.status_code != 200:
                return False  # Not an org or doesn't exist

            # Check membership
            membership_url = f"https://api.github.com/orgs/{org_name}/members/{username}"
            membership_response = self.session.get(membership_url, headers=self.headers, timeout=10)

            return membership_response.status_code == 204  # 204 means member, 404 means not

        except Exception:
            return False

    def get_maintainer_contributors(self, repo: Dict, max_contributors: int = 10) -> List[Dict]:
        """Get maintainers and core contributors for a repo based on recent activity"""
        contributors = []
        if not repo or 'owner' not in repo or 'name' not in repo:
            return contributors
        owner = repo.get('owner', {}).get('login', '')
        repo_name = repo.get('name', '')
        repo_full_name = repo.get('full_name', f'{owner}/{repo_name}' if owner and repo_name else 'unknown/unknown')
        if not owner or not repo_name:
            return contributors

        try:
            # Get recent contributors via commits API (more reliable than contributors endpoint)
            commits_url = f"https://api.github.com/repos/{repo_full_name}/commits"
            params = {
                'per_page': min(max_contributors * 3, 100),  # Get more to filter
                'since': days_ago(90)
            }

            response = self.session.get(commits_url, headers=self.headers, params=params, timeout=10)

            if self._rate_limit_wait(response):
                response = self.session.get(commits_url, headers=self.headers, params=params, timeout=10)

            if response.status_code == 200:
                commits = response.json()
                author_counts = {}

                # Count commits by author
                for commit in commits:
                    if commit.get('author') and commit['author']['type'] == 'User':
                        author_login = commit['author']['login']
                        author_counts[author_login] = author_counts.get(author_login, 0) + 1

                # Sort by commit count and get top contributors
                sorted_authors = sorted(author_counts.items(), key=lambda x: x[1], reverse=True)

                for login, commit_count in sorted_authors[:max_contributors]:
                    # Get maintainer status for this user
                    maintainer_info = self.check_maintainer_status(repo_full_name, login)

                    # Get user details
                    user_details = self.get_user_details(login)

                    contributor_data = {
                        'user': {
                            'login': login,
                            'type': 'User',
                            'id': user_details.get('id')
                        },
                        'signal': f"Core contributor: {commit_count} commits in last 90 days",
                        'signal_type': 'core_contributor',
                        'signal_at': to_utc_iso8601(utc_now()),
                        'commit_count_90d': commit_count,
                        'maintainer_status': maintainer_info,
                        'url': f"https://github.com/{repo_full_name}/commits?author={login}"
                    }

                    contributors.append(contributor_data)

        except Exception as e:
            # Fallback to basic PR/commit authors if contributor analysis fails
            pass

        return contributors

    def process_repo_concurrent(self, repo: Dict) -> ProcessingResult:
        """Process a single repository for concurrent processing"""
        repo_full_name = repo.get('full_name') or 'unknown/unknown'
        start_time = time.time()

        try:
            prospects = []

            # First, try to get maintainers and core contributors (higher quality)
            maintainer_authors = self.get_maintainer_contributors(repo, max_contributors=8)

            if maintainer_authors:
                for author_data in maintainer_authors:
                    prospect = self.create_prospect(author_data, repo)
                    if prospect:
                        prospects.append(prospect)

            # Fallback to PR authors if we need more prospects
            if len(maintainer_authors) < 3:
                pr_authors = self.get_pr_authors(repo)

                if pr_authors:
                    for author_data in pr_authors:
                        # Skip if we already processed this user as maintainer
                        login = author_data.get('user', {}).get('login') if author_data else None
                        if login and any(p.login == login for p in prospects):
                            continue

                        prospect = self.create_prospect(author_data, repo)
                        if prospect:
                            prospects.append(prospect)

            # Get commit authors as last resort
            commit_authors = self.get_commit_authors(repo)

            if commit_authors:
                for author_data in commit_authors:
                    # Skip if we already processed this user
                    login = author_data.get('user', {}).get('login') if author_data else None
                    if login and any(p.login == login for p in prospects):
                        continue

                    prospect = self.create_prospect(author_data, repo)
                    if prospect:
                        prospects.append(prospect)

            # Convert prospects to dicts for serialization
            prospect_dicts = [p.to_dict() for p in prospects if p]

            return ProcessingResult(
                repo_full_name=repo_full_name,
                success=True,
                prospects=prospect_dicts,
                processing_time=time.time() - start_time
            )

        except Exception as e:
            return ProcessingResult(
                repo_full_name=repo_full_name,
                success=False,
                prospects=[],
                error=str(e),
                processing_time=time.time() - start_time
            )
    
    def parse_github_url(self, url: str) -> Dict:
        """Parse GitHub URL to extract user/repo information"""
        if not url:
            return {}
        # Clean up URL
        url = url.strip()
        if url.startswith('@'):
            url = url[1:]
        if not url.startswith('http'):
            url = f"https://{url}"
            
        parsed = urlparse(url)
        if parsed.netloc != 'github.com':
            raise ValueError(f"Invalid GitHub URL: {url}")
            
        path_parts = [p for p in parsed.path.split('/') if p]
        
        if len(path_parts) == 0:
            raise ValueError("Invalid GitHub URL: no user or repo specified")
        elif len(path_parts) == 1:
            # User profile URL
            return {'type': 'user', 'username': path_parts[0]}
        elif len(path_parts) >= 2:
            # Repository URL
            return {'type': 'repo', 'owner': path_parts[0], 'repo': path_parts[1]}
        else:
            raise ValueError(f"Invalid GitHub URL format: {url}")
    
    def get_user_repos(self, username: str, limit: int = 10) -> List[Dict]:
        """Get user's repositories"""
        url = f"https://api.github.com/users/{username}/repos"
        params = {
            'sort': 'updated',
            'direction': 'desc',
            'per_page': min(limit, 100)
        }
        
        response = self.session.get(url, headers=self.headers, params=params, timeout=10)
        
        if self._rate_limit_wait(response):
            response = self.session.get(url, headers=self.headers, params=params, timeout=10)
            
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching user repos: {response.status_code}")
            return []
    
    def scrape_from_url(self, github_url: str):
        """Scrape prospects from a GitHub URL (user profile or repository)"""
        # Set URL mode flag to allow prospects without emails
        self._url_mode = True
        try:
            parsed = self.parse_github_url(github_url)
            if parsed['type'] == 'user':
                username = parsed['username']
                
                # Get user details first
                user_details = self.get_user_details(username)
                if not user_details:
                    tqdm.write(f"❌ User {username} not found")
                    return
                
                # Get user's repositories
                repos = self.get_user_repos(username, limit=10)
                
                # Create a prospect from the user's most recent activity
                if repos:
                    # Use the most recently updated repo as context
                    recent_repo = repos[0]
                    
                    # Create author data for this user
                    author_data = {
                        'user': {
                            'login': username,
                            'type': 'User'
                        },
                        'signal': f"owns repository: {recent_repo['name']}",
                        'signal_type': 'repo_owner',
                        'signal_at': recent_repo.get('updated_at', datetime.now().isoformat())
                    }
                    
                    prospect = self.create_prospect(author_data, recent_repo)
                    if prospect:
                        self.all_prospects.append(prospect)
                
            elif parsed['type'] == 'repo':
                owner = parsed['owner']
                repo_name = parsed['repo']
                
                # Get repository details
                repo_url = f"https://api.github.com/repos/{owner}/{repo_name}"
                response = self.session.get(repo_url, headers=self.headers, timeout=10)
                
                if self._rate_limit_wait(response):
                    response = self.session.get(repo_url, headers=self.headers, timeout=10)
                
                if response.status_code != 200:
                    tqdm.write(f"❌ Repository {owner}/{repo_name} not found")
                    return
                
                repo = response.json()
                
                # Get contributors from this specific repo
                pr_authors = self.get_pr_authors(repo)
                commit_authors = self.get_commit_authors(repo)
                
                # Process all authors with progress bar
                all_authors = pr_authors + commit_authors
                if all_authors:
                    pbar = tqdm(all_authors, desc=f"Processing {repo['full_name']}", unit="author")
                    for author_data in pbar:
                        prospect = self.create_prospect(author_data, repo)
                        if prospect:
                            self.all_prospects.append(prospect)
                            pbar.set_description(f"Added {prospect.login}")
                        
        except Exception as e:
            tqdm.write(f"❌ Error processing URL {github_url}: {e}")
    
    def print_prospects_summary(self):
        """Print a summary of all found prospects"""
        if not self.all_prospects:
            print("\n📭 No prospects found")
            return
            
        print(f"\n📊 PROSPECT SUMMARY ({len(self.all_prospects)} total)")
        print("=" * 80)
        
        for i, prospect in enumerate(self.all_prospects, 1):
            email = prospect.get_best_email()
            linkedin = prospect.get_linkedin()
            
            print(f"\n{i:2d}. {prospect.login} ({prospect.name or 'No name'})")
            print(f"    👤 GitHub: {prospect.github_user_url}")
            print(f"    📧 Email: {email or 'No email found'}")
            print(f"    🏢 Company: {prospect.company or 'Not specified'}")
            print(f"    📍 Location: {prospect.location or 'Not specified'}")
            print(f"    🔗 LinkedIn: {linkedin or 'Not found'}")
            print(f"    ⭐ GitHub Stats: {prospect.followers or 0} followers, {prospect.public_repos or 0} repos")
            print(f"    📦 Repository: {prospect.repo_full_name} ({prospect.stars} stars)")
            print(f"    📦 Repo URL: {prospect.github_repo_url}")
            print(f"    🎯 Signal: {prospect.signal}")
            print(f"    📅 Activity: {prospect.signal_at}")
            
            if prospect.bio:
                bio_short = prospect.bio[:100] + "..." if len(prospect.bio) > 100 else prospect.bio
                print(f"    💭 Bio: {bio_short}")
        
        print("\n" + "=" * 80)
        
        # Summary stats
        with_email = sum(1 for p in self.all_prospects if p.has_email())
        with_company = sum(1 for p in self.all_prospects if p.company)
        with_linkedin = sum(1 for p in self.all_prospects if p.get_linkedin())
        
        print(f"📈 STATS:")
        print(f"   • {with_email}/{len(self.all_prospects)} have email addresses ({with_email/len(self.all_prospects)*100:.1f}%)")
        print(f"   • {with_company}/{len(self.all_prospects)} have company info ({with_company/len(self.all_prospects)*100:.1f}%)")
        print(f"   • {with_linkedin}/{len(self.all_prospects)} have LinkedIn ({with_linkedin/len(self.all_prospects)*100:.1f}%)")
        
        # Top companies
        companies = [p.company for p in self.all_prospects if p.company]
        if companies:
            from collections import Counter
            top_companies = Counter(companies).most_common(5)
            print(f"\n🏢 TOP COMPANIES:")
            for company, count in top_companies:
                print(f"   • {company}: {count} prospects")
        
        print(f"\n💾 Data saved to: {self.output_path or 'No output file specified'}")
        print("=" * 80)
        
    def create_prospect(self, author_data: Dict, repo: Dict) -> Optional[Prospect]:
        """Create a Prospect object from author and repo data"""
        if not author_data or 'user' not in author_data:
            return None
        user = author_data['user']
        if not user or not isinstance(user, dict):
            return None
        
        # Dedup: skip if we've seen this login before
        login_val = user.get('login')
        if not login_val or self._dedup_seen(login_val):
            return None
        
        # Generate stable lead_id
        repo_full_name = repo.get('full_name', 'unknown/unknown')
        lead_id = hashlib.md5(f"{login_val}_{repo_full_name}".encode()).hexdigest()[:12]
        
        # Skip if we've already seen this lead
        if lead_id in self.prospects:
            return None
        
        # Get full user details
        user_details = self.get_user_details(user['login'])

        # Get maintainer status information
        maintainer_status = author_data.get('maintainer_status', {})
        is_maintainer = maintainer_status.get('is_maintainer', False)
        is_org_member = maintainer_status.get('is_org_member', False)
        is_codeowner = maintainer_status.get('is_codeowner', False)
        permission_level = maintainer_status.get('permission_level', 'read')
        commit_count_90d = author_data.get('commit_count_90d')

        # Extract emails
        email_commit = author_data.get('email')
        email_profile = user_details.get('email')
        
        # Inclusion policy: include prospects even without emails unless explicitly configured to skip
        skip_without_email = self.config.get('filters', {}).get('skip_without_email', False)
        if skip_without_email and not (email_commit or email_profile):
            return None
        
        # Extract LinkedIn from blog URL if present
        linkedin_username = None
        blog_url = user_details.get('blog', '')
        if blog_url and 'linkedin.com/in/' in blog_url:
            linkedin_username = blog_url.split('linkedin.com/in/')[-1].split('/')[0].split('?')[0]

        # Enhanced contact enrichment
        best_email = self._choose_main_email(user_details.get('email'), email_commit)

        # Calculate contactability score
        contactability_score = 0
        if best_email:
            contactability_score += 30
            if user_details.get('email'):  # Profile email preferred
                contactability_score += 10
        if linkedin_username:
            contactability_score += 30

        # Extract corporate domain
        corporate_domain = self._extract_corporate_domain(best_email, blog_url, user_details.get('company'))

        # Determine email type
        email_type = 'unknown'
        if best_email:
            email_type = self._determine_email_type(best_email)

        # Check for disposable email
        is_disposable = False
        if best_email:
            is_disposable = self._is_disposable_email(best_email)

        # Generate LinkedIn query for future resolution
        linkedin_query = None
        if not linkedin_username and user_details.get('name'):
            # Create a search query for LinkedIn lookup in Phase 2
            name = user_details.get('name', '') or ''
            company = user_details.get('company', '') or ''
            linkedin_query = f"{name} {company} site:linkedin.com/in/".strip()
        
        # Extract pronouns (often in bio or name field)
        pronouns = None
        if user_details.get('bio') and isinstance(user_details['bio'], str):
            bio_lower = user_details.get('bio', '').lower()
            if 'he/him' in bio_lower:
                pronouns = 'he/him'
            elif 'she/her' in bio_lower:
                pronouns = 'she/her'
            elif 'they/them' in bio_lower:
                pronouns = 'they/them'
        
        # Get contribution stats (GraphQL) with caching
        try:
            contribs = self.get_user_contributions(user['login'])
        except Exception:
            contribs = None
        contributions_last_year = (contribs or {}).get('contributions_last_year')
        total_contributions = (contribs or {}).get('total_contributions')
        
        prospect = Prospect(
            # Core identification
            lead_id=lead_id,
            login=user['login'],
            id=user_details.get('id'),
            node_id=user_details.get('node_id'),

            # Personal info
            name=user_details.get('name'),
            company=user_details.get('company'),
            email_public_commit=email_commit,
            email_profile=email_profile,
            location=user_details.get('location'),
            bio=user_details.get('bio'),
            pronouns=pronouns,

            # Repository context
            repo_full_name=repo['full_name'],
            repo_description=repo.get('description'),
            signal=author_data['signal'],
            signal_type=author_data['signal_type'],
            signal_at=author_data['signal_at'],
            topics=','.join(repo.get('topics', [])),
            language=repo.get('language', ''),
            stars=int(repo.get('stargazers_count', 0) or 0),
            forks=int(repo.get('forks_count', 0) or 0),
            watchers=int(repo.get('watchers_count', 0) or 0),

            # Maintainer status
            is_maintainer=is_maintainer,
            is_org_member=is_org_member,
            is_codeowner=is_codeowner,
            permission_level=permission_level,
            commit_count_90d=commit_count_90d,

            # Contact enrichment
            contactability_score=contactability_score,
            email_type=email_type,
            is_disposable_email=is_disposable,
            corporate_domain=corporate_domain,
            linkedin_query=linkedin_query,

            # URLs
            github_user_url=f"https://github.com/{user['login']}",
            github_repo_url=f"https://github.com/{repo['full_name']}",
            avatar_url=user_details.get('avatar_url'),
            html_url=user_details.get('html_url'),
            api_url=user_details.get('url'),
            followers_url=user_details.get('followers_url'),
            following_url=user_details.get('following_url'),
            gists_url=user_details.get('gists_url'),
            starred_url=user_details.get('starred_url'),
            subscriptions_url=user_details.get('subscriptions_url'),
            organizations_url=user_details.get('organizations_url'),
            repos_url=user_details.get('repos_url'),
            events_url=user_details.get('events_url'),
            received_events_url=user_details.get('received_events_url'),

            # Social/Professional
            twitter_username=user_details.get('twitter_username'),
            blog=user_details.get('blog'),
            linkedin_username=linkedin_username,
            hireable=user_details.get('hireable'),

            # GitHub Statistics
            public_repos=user_details.get('public_repos'),
            public_gists=user_details.get('public_gists'),
            followers=user_details.get('followers'),
            following=user_details.get('following'),
            total_private_repos=user_details.get('total_private_repos'),
            owned_private_repos=user_details.get('owned_private_repos'),
            private_gists=user_details.get('private_gists'),
            disk_usage=user_details.get('disk_usage'),
            collaborators=user_details.get('collaborators'),

            # Contribution data
            contributions_last_year=contributions_last_year,
            total_contributions=total_contributions,
            longest_streak=None,
            current_streak=None,

            # Account metadata
            created_at=user_details.get('created_at'),
            updated_at=user_details.get('updated_at'),
            type=user_details.get('type'),
            site_admin=user_details.get('site_admin'),
            gravatar_id=user_details.get('gravatar_id'),
            suspended_at=user_details.get('suspended_at'),

            # Plan information
            plan_name=user_details.get('plan', {}).get('name') if user_details.get('plan') else None,
            plan_space=user_details.get('plan', {}).get('space') if user_details.get('plan') else None,
            plan_collaborators=user_details.get('plan', {}).get('collaborators') if user_details.get('plan') else None,
            plan_private_repos=user_details.get('plan', {}).get('private_repos') if user_details.get('plan') else None,

            # Additional flags
            two_factor_authentication=user_details.get('two_factor_authentication'),
            has_organization_projects=user_details.get('has_organization_projects'),
            has_repository_projects=user_details.get('has_repository_projects')
        )
        
        self.prospects.add(lead_id)
        # Count as a lead only if we have an email
        if prospect.email_profile or prospect.email_public_commit or prospect.get_best_email():
            self.leads_with_email_count += 1
        
        # Write to CSV immediately if incremental writing is enabled
        if self.output_path:
            self._write_prospect_to_csv(prospect)
        
        # Score the prospect before saving
        prospect_dict = prospect.to_dict()
        scoring_result = self.prospect_scorer.score_prospect(prospect_dict, repo)

        # Update prospect with scoring results
        prospect.prospect_score = scoring_result.total_score
        prospect.prospect_tier = scoring_result.tier
        prospect.scoring_components = scoring_result.component_scores
        prospect.risk_factors = scoring_result.risk_factors
        prospect.priority_signals = scoring_result.priority_signals
        prospect.cohort = scoring_result.cohort

        # Update prospect with compliance results
        if scoring_result.compliance_result:
            compliance = scoring_result.compliance_result
            prospect.compliance_risk_level = compliance.risk_level
            prospect.compliance_blocked = self.prospect_scorer.compliance_checker.should_block_prospect(compliance)
            prospect.compliance_risk_factors = compliance.risk_factors
            prospect.geo_location = compliance.geo_location

        # Apply tier-based filtering - reject low-quality prospects
        if scoring_result.tier == 'REJECT':
            return None  # Don't include rejected prospects

        # Build Attio object rows
        self._upsert_person_record(user_details, user['login'], email_commit, repo)
        self._upsert_repo_record(repo)
        self._add_membership_record(user['login'], repo, author_data.get('signal_at'))
        self._add_signal_record(user['login'], repo, author_data)
        # Mirror latest signal onto the People row with `signals_*` fields
        try:
            self._update_person_with_signal(user['login'], repo, author_data)
        except Exception:
            pass

        # Mark login as seen in dedup DB
        self._dedup_mark(user['login'])
            
        return prospect

    def _upsert_person_record(self, user_details: Dict, login: str, email_public_commit: Optional[str] = None, repo: Optional[Dict] = None):
        """Create or update a People row keyed by login."""
        if login in self.people_records:
            # Fill commit email if missing and a new one is provided
            if email_public_commit and not self.people_records[login].get('email_public_commit'):
                self.people_records[login]['email_public_commit'] = email_public_commit
            # Backfill company_domain if missing
            if not self.people_records[login].get('company_domain'):
                company_domain_existing = None
                email_profile = user_details.get('email')
                if email_profile:
                    company_domain_existing = self._normalize_domain(email_profile)
                if not company_domain_existing and email_public_commit:
                    company_domain_existing = self._normalize_domain(email_public_commit)
                if not company_domain_existing and repo:
                    owner_login = (repo.get('owner') or {}).get('login')
                    owner_type = (repo.get('owner') or {}).get('type')
                    if owner_login and owner_type == 'Organization':
                        org = self._get_org_details(owner_login)
                        company_domain_existing = self._normalize_domain(org.get('blog')) or company_domain_existing
                    if not company_domain_existing:
                        company_domain_existing = self._normalize_domain(repo.get('homepage'))
                if company_domain_existing:
                    self.people_records[login]['company_domain'] = company_domain_existing
            return
        # Infer pronouns from bio when available
        pronouns = None
        bio_lower = (user_details.get('bio') or '').lower()
        if 'he/him' in bio_lower:
            pronouns = 'he/him'
        elif 'she/her' in bio_lower:
            pronouns = 'she/her'
        elif 'they/them' in bio_lower:
            pronouns = 'they/them'
        # Derive company_domain
        company_domain = None
        email_profile = user_details.get('email')
        if email_profile:
            dom = self._normalize_domain(email_profile)
            if dom and not self._is_public_email_domain(dom):
                company_domain = dom
        if not company_domain and email_public_commit:
            dom = self._normalize_domain(email_public_commit)
            if dom and not self._is_public_email_domain(dom):
                company_domain = dom
        if not company_domain and repo:
            owner_login = (repo.get('owner') or {}).get('login')
            owner_type = (repo.get('owner') or {}).get('type')
            if owner_login and owner_type == 'Organization':
                org = self._get_org_details(owner_login)
                dom = self._normalize_domain(org.get('blog'))
                if dom and not self._is_public_email_domain(dom):
                    company_domain = dom
            if not company_domain:
                dom = self._normalize_domain(repo.get('homepage'))
                if dom and not self._is_public_email_domain(dom):
                    company_domain = dom

        person_row = {
            'login': login,
            'id': user_details.get('id'),
            'node_id': user_details.get('node_id'),
            # Internal lead hash for person-level row (stable by login)
            'lead_id': hashlib.md5(login.encode()).hexdigest()[:12],
            'name': user_details.get('name'),
            'company': user_details.get('company'),
            'email_profile': user_details.get('email'),
            'email_public_commit': email_public_commit,
            'email_main': self._choose_main_email(user_details.get('email'), email_public_commit),
            'company_domain': company_domain,
            'Predicted Email': '',
            'location': user_details.get('location'),
            'bio': user_details.get('bio'),
            'pronouns': pronouns,
            # Helpful context copied from latest repo processed for this user
            'recent_repo_full_name': (repo or {}).get('full_name') if repo else None,
            'recent_repo_stars': (repo or {}).get('stargazers_count') if repo else None,
            'public_repos': user_details.get('public_repos'),
            'public_gists': user_details.get('public_gists'),
            'followers': user_details.get('followers'),
            'following': user_details.get('following'),
            'created_at': user_details.get('created_at'),
            'updated_at': user_details.get('updated_at'),
            'html_url': user_details.get('html_url'),
            'avatar_url': user_details.get('avatar_url'),
            'github_user_url': f"https://github.com/{login}",
            'api_url': user_details.get('url')
        }
        self.people_records[login] = person_row

    def _sanitize_signal_type(self, raw: Optional[str]) -> str:
        """Normalize signal_type to allowed set: pr|issue|commit|release|star|fork|other"""
        allowed = {"pr", "issue", "commit", "release", "star", "fork", "other"}
        if not raw:
            return "other"
        r = str(raw).lower().strip()
        if r in allowed:
            return r
        alias_map = {
            "pull_request": "pr",
            "pull": "pr",
            "merge_request": "pr",
            "stargazer": "star",
            "starred": "star",
            "forked": "fork",
            "forks": "fork",
            "repo_owner": "other",
            "owner": "other",
            "created_repo": "other",
        }
        return alias_map.get(r, "other")

    def _fetch_repo_details(self, full_name: str) -> Dict:
        """Fetch full repo details (subscribers_count, default_branch, homepage, flags). Cached."""
        if full_name in self.repo_details_cache:
            return self.repo_details_cache[full_name]
        url = f"https://api.github.com/repos/{full_name}"
        resp = self.session.get(url, headers=self.headers, timeout=10)
        if self._rate_limit_wait(resp):
            resp = self.session.get(url, headers=self.headers, timeout=10)
        details = resp.json() if resp.status_code == 200 else {}
        self.repo_details_cache[full_name] = details
        return details

    def _count_open_prs(self, full_name: str) -> Optional[int]:
        """Use search API to count open PRs without paging full lists."""
        try:
            q = f"repo:{full_name} is:pr is:open"
            resp = self.session.get("https://api.github.com/search/issues",
                                    headers=self.headers,
                                    params={"q": q, "per_page": 1}, timeout=10)
            if self._rate_limit_wait(resp):
                resp = self.session.get("https://api.github.com/search/issues",
                                        headers=self.headers,
                                        params={"q": q, "per_page": 1}, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("total_count", 0)
        except Exception:
            return None
        return None

    def _get_releases_info(self, full_name: str) -> (Optional[int], Optional[str]):
        """Return (releases_count, last_release_at)."""
        try:
            url = f"https://api.github.com/repos/{full_name}/releases"
            resp = self.session.get(url, headers=self.headers, params={"per_page": 1}, timeout=10)
            if self._rate_limit_wait(resp):
                resp = self.session.get(url, headers=self.headers, params={"per_page": 1}, timeout=10)
            if resp.status_code != 200:
                return None, None
            releases = resp.json()
            last_release_at = releases[0].get('published_at') if releases else None
            # Parse Link header for count if present
            link = resp.headers.get('Link')
            if link and 'rel="last"' in link:
                try:
                    last_part = [p for p in link.split(',') if 'rel="last"' in p][0]
                    page_val = re.search(r"[?&]page=(\d+)", last_part)
                    if page_val:
                        return int(page_val.group(1)), last_release_at
                except Exception:
                    pass
            return (len(releases) if releases is not None else None), last_release_at
        except Exception:
            return None, None

    def _count_contributors(self, full_name: str) -> Optional[int]:
        """Estimate contributors by paging header."""
        try:
            url = f"https://api.github.com/repos/{full_name}/contributors"
            resp = self.session.get(url, headers=self.headers, params={"per_page": 1, "anon": True}, timeout=10)
            if self._rate_limit_wait(resp):
                resp = self.session.get(url, headers=self.headers, params={"per_page": 1, "anon": True}, timeout=10)
            if resp.status_code != 200:
                return None
            link = resp.headers.get('Link')
            if link and 'rel="last"' in link:
                last_part = [p for p in link.split(',') if 'rel="last"' in p][0]
                page_val = re.search(r"[?&]page=(\d+)", last_part)
                if page_val:
                    return int(page_val.group(1))
            return len(resp.json())
        except Exception:
            return None

    def _upsert_repo_record(self, repo: Dict):
        """Create or update a Repos row keyed by repo_full_name."""
        full_name = repo.get('full_name', 'unknown/unknown')
        if full_name in self.repo_records:
            return
        # recent push in last 30 days
        pushed_at = repo.get('pushed_at')
        recent_push_30d = False
        try:
            if pushed_at:
                pushed_dt = datetime.fromisoformat(pushed_at.replace('Z', '+00:00'))
                recent_push_30d = (datetime.now(pushed_dt.tzinfo) - pushed_dt) <= timedelta(days=30)
        except Exception:
            recent_push_30d = False
        # Optional enrichment
        pull_cfg = self.config.get('enrichment', {}).get('pull', {}) if isinstance(self.config, dict) else {}
        details = {}
        if pull_cfg:
            # fetch details once to populate subscribers_count and flags
            details = self._fetch_repo_details(full_name)
        open_prs = self._count_open_prs(full_name) if pull_cfg else None
        releases_count, last_release_at = self._get_releases_info(full_name) if pull_cfg else (None, None)
        contributors_count = self._count_contributors(full_name) if pull_cfg else None

        # Derive company_domain from org blog or repo homepage
        company_domain = None
        owner_login = (repo.get('owner') or {}).get('login')
        owner_type = (repo.get('owner') or {}).get('type')
        if owner_login and owner_type == 'Organization':
            try:
                org = self._get_org_details(owner_login)
                dom = self._normalize_domain((org or {}).get('blog'))
                if dom and not self._is_public_email_domain(dom):
                    company_domain = dom
            except Exception:
                company_domain = None
        if not company_domain:
            dom = self._normalize_domain((details or {}).get('homepage') or repo.get('homepage'))
            if dom and not self._is_public_email_domain(dom):
                company_domain = dom

        repo_row = {
            'repo_id': repo.get('id'),
            'repo_full_name': full_name,
            'repo_name': repo.get('name'),
            'owner_login': repo.get('owner', {}).get('login'),
            'owner_type': (repo.get('owner', {}) or {}).get('type'),
            'host': 'GitHub',
            'description': repo.get('description'),
            'primary_language': repo.get('language') or '',
            'license': (repo.get('license') or {}).get('name') if repo.get('license') else None,
            'license_spdx': (repo.get('license') or {}).get('spdx_id') if repo.get('license') else None,
            'topics': ','.join(repo.get('topics', [])),
            'default_branch': details.get('default_branch') or repo.get('default_branch'),
            'homepage': details.get('homepage') or repo.get('homepage'),
            'has_issues': details.get('has_issues', repo.get('has_issues')),
            'has_discussions': details.get('has_discussions'),
            'company_domain': company_domain,
            'stars': int(repo.get('stargazers_count', 0) or 0),
            'watchers': int(repo.get('watchers_count', 0) or 0),
            'subscribers': int(details.get('subscribers_count', 0) or 0),
            'forks': int(repo.get('forks_count', 0) or 0),
            'open_issues': repo.get('open_issues_count'),
            'open_prs': open_prs,
            'releases_count': releases_count,
            'last_release_at': last_release_at,
            'num_contributors': contributors_count,
            'is_fork': repo.get('fork', False),
            'is_archived': repo.get('archived', False),
            'recent_push_30d': recent_push_30d,
            'created_at': repo.get('created_at'),
            'updated_at': repo.get('updated_at'),
            'pushed_at': repo.get('pushed_at'),
            'html_url': repo.get('html_url'),
            'api_url': repo.get('url')
        }
        self.repo_records[full_name] = repo_row

    def _add_membership_record(self, login: str, repo: Dict, last_activity_at: Optional[str]):
        """Add a Membership row keyed by membership_id."""
        repo_full_name = repo.get('full_name') or 'unknown/unknown'
        repo_id = repo.get('id')
        membership_id = hashlib.md5(f"{repo_id}:{login}".encode()).hexdigest()[:16]
        if membership_id in self.membership_records:
            # Update last_activity_at if newer
            if last_activity_at and (
                not self.membership_records[membership_id].get('last_activity_at') or
                last_activity_at > self.membership_records[membership_id].get('last_activity_at')
            ):
                self.membership_records[membership_id]['last_activity_at'] = last_activity_at
            return
        self.membership_records[membership_id] = {
            'membership_id': membership_id,
            'login': login,
            'repo_id': repo_id,
            'repo_full_name': repo_full_name,
            'role': '',  # can be AI classified later
            'permission': '',
            'affiliation': '',
            'is_org_member': None,
            'contributions_past_year': None,
            'last_activity_at': last_activity_at
        }

    def _add_signal_record(self, login: str, repo: Dict, author_data: Dict):
        """Add a Signal row keyed by signal_id."""
        signal_at = author_data.get('signal_at') or ''
        signal_type = self._sanitize_signal_type(author_data.get('signal_type'))
        signal_text = author_data.get('signal') or ''
        repo_full_name = repo.get('full_name') or 'unknown/unknown'
        repo_id = repo.get('id')
        raw_id = f"{login}:{repo_full_name}:{signal_at}:{signal_type}:{signal_text[:20]}"
        signal_id = hashlib.md5(raw_id.encode()).hexdigest()[:16]
        if signal_id in self.signal_records:
            return
        self.signal_records[signal_id] = {
            'signal_id': signal_id,
            'login': login,
            'repo_id': repo_id,
            'repo_full_name': repo_full_name,
            'signal_type': signal_type,
            'signal': signal_text,
            'signal_at': signal_at,
            'url': author_data.get('url'),
            'html_url': author_data.get('url'),
            'source': 'GitHub'
        }

    def _update_person_with_signal(self, login: str, repo: Dict, author_data: Dict):
        """Copy the latest signal details onto the person row with signals_* fields."""
        if login not in self.people_records:
            return
        signal_at = author_data.get('signal_at') or ''
        signal_type = self._sanitize_signal_type(author_data.get('signal_type'))
        signal_text = author_data.get('signal') or ''
        repo_full_name = repo.get('full_name')
        repo_id = repo.get('id')
        raw_id = f"{login}:{repo_full_name}:{signal_at}:{signal_type}:{signal_text[:20]}"
        signal_id = hashlib.md5(raw_id.encode()).hexdigest()[:16]
        self.people_records[login].update({
            'signals_signal_id': signal_id,
            'signals_signal_type': signal_type,
            'signals_signal': signal_text,
            'signals_signal_at': signal_at,
            'signals_html_url': author_data.get('url'),
            'signals_source': 'GitHub',
            'signals_repo_full_name': repo_full_name,
            'signals_repo_id': repo_id,
        })
        
    def scrape(self):
        """Main scraping logic with job tracking"""
        # Start job tracking
        search_query = self._build_icp_query()
        job = self.job_tracker.start_job(
            search_query=search_query,
            config=self.config,
            icp_config=self.icp_config,
            github_token=self.token or os.environ.get('GITHUB_TOKEN', '')
        )

        print(f"🚀 Started job: {job.job_id}")
        print(f"🔎 Query: {search_query[:100]}...")
        print(f"📊 Window: {job.window_days}d | Max repos: {job.max_repos} | Max leads: {job.max_leads}")

        # Initialize CSV file for incremental writing
        if self.output_path:
            self._init_csv_file()

        repos = self.search_repos()
        print(f"📦 Repos returned: {len(repos)}")

        # Update job stats
        job.stats.total_repos_processed = len(repos)

        # Check if concurrent processing is enabled
        concurrency_enabled = self.config.get('concurrency', {}).get('enabled', False)

        if concurrency_enabled and len(repos) > 1:
            # Use concurrent processing
            print(f"🚀 Processing {len(repos)} repos concurrently with {self.concurrent_processor.max_workers} workers")
            processing_results = self.concurrent_processor.process_repositories_concurrent(
                repos, self.process_repo_concurrent
            )

            # Process results
            total_prospects = 0
            successful_repos = 0
            cache_stats = self.concurrent_processor.get_cache_stats()

            for result in processing_results:
                if result.success:
                    successful_repos += 1
                    # Convert dicts back to Prospect objects
                    for prospect_dict in result.prospects:
                        # Create a temporary Prospect object from dict
                        prospect = Prospect(**prospect_dict)
                        self.all_prospects.append(prospect)
                        if prospect.has_email():
                            self.leads_with_email_count += 1
                        total_prospects += 1
                else:
                    print(f"❌ Failed to process {result.repo_full_name}: {result.error}")
                    job.stats.errors.append(f"Failed to process {result.repo_full_name}: {result.error}")

            # Update job stats
            job.stats.raw_prospects_found = total_prospects
            job.stats.cache_hits = cache_stats.get('cache_files', 0)
            job.stats.cache_misses = len(processing_results) - cache_stats.get('cache_files', 0)

            print(f"📊 Concurrent processing complete: {total_prospects} prospects from {successful_repos}/{len(processing_results)} repos")

        else:
            # Use traditional sequential processing
            print(f"🔄 Processing {len(repos)} repos sequentially")

            # Use tqdm for progress tracking
            repo_pbar = tqdm(repos, desc="Processing repos", unit="repo")

            for repo in repo_pbar:
                repo_pbar.set_description(f"Processing {repo['full_name']}")

                # First, try to get maintainers and core contributors (higher quality)
                maintainer_authors = self.get_maintainer_contributors(repo, max_contributors=8)

                if maintainer_authors:
                    maintainer_pbar = tqdm(maintainer_authors, desc="  Core contributors", unit="author", leave=False)
                    for author_data in maintainer_pbar:
                        prospect = self.create_prospect(author_data, repo)
                        if prospect:
                            self.all_prospects.append(prospect)
                            maintainer_pbar.set_description(f"  Added {prospect.login}")

                # Fallback to PR authors if we need more prospects
                if self.config['limits']['per_repo_prs'] > 0 and len(maintainer_authors) < 3:
                    pr_authors = self.get_pr_authors(repo)

                    if pr_authors:
                        pr_pbar = tqdm(pr_authors, desc="  PR authors", unit="author", leave=False)
                        for author_data in pr_pbar:
                            # Skip if we already processed this user as maintainer
                            login = author_data.get('user', {}).get('login') if author_data else None
                            if any(p.login == login for p in self.all_prospects):
                                continue

                            prospect = self.create_prospect(author_data, repo)
                            if prospect:
                                self.all_prospects.append(prospect)
                                pr_pbar.set_description(f"  Added {prospect.login}")

                # Get commit authors as last resort
                if self.config['limits']['per_repo_commits'] > 0:
                    commit_authors = self.get_commit_authors(repo)

                    if commit_authors:
                        commit_pbar = tqdm(commit_authors, desc="  Commit authors", unit="author", leave=False)
                        for author_data in commit_pbar:
                            # Skip if we already processed this user
                            login = author_data.get('user', {}).get('login') if author_data else None
                            if any(p.login == login for p in self.all_prospects):
                                continue

                            prospect = self.create_prospect(author_data, repo)
                            if prospect:
                                self.all_prospects.append(prospect)
                                commit_pbar.set_description(f"  Added {prospect.login}")

                # Update main progress bar with current stats (leads = with email)
                repo_pbar.set_postfix(prospects=len(self.all_prospects), leads=self.leads_with_email_count)

                # Check if we've hit our leads (people with email) limit
                if self.leads_with_email_count >= self.config['limits']['max_people']:
                    repo_pbar.set_description(f"Reached max leads limit ({self.config['limits']['max_people']})")
                    print(f"✅ Stopping early: collected {self.leads_with_email_count} leads (target {self.config['limits']['max_people']})")
                    break

                # Be nice to GitHub
                time.sleep(self.config.get('delay', 1))

            repo_pbar.close()

            # Update job stats for sequential processing
            job.stats.raw_prospects_found = len(self.all_prospects)
            job.stats.contactable_prospects = self.leads_with_email_count
        
        # Perform identity deduplication
        if self.all_prospects:
            print(f"\n🔄 Deduplicating {len(self.all_prospects)} prospects...")
            prospect_dicts = [p.to_dict() for p in self.all_prospects]
            deduplicated_dicts = self.identity_deduper.deduplicate_prospects(prospect_dicts)

            # Convert back to Prospect objects
            deduplicated_prospects = []
            for prospect_dict in deduplicated_dicts:
                try:
                    prospect = Prospect(**prospect_dict)
                    deduplicated_prospects.append(prospect)
                except Exception as e:
                    print(f"⚠️  Error converting deduplicated prospect: {e}")
                    continue

            self.all_prospects = deduplicated_prospects

            # Update job stats with deduplication info
            dedupe_stats = self.identity_deduper.get_merge_stats()
            job.stats.raw_prospects_found = dedupe_stats['total_prospects_processed']
            job.stats.prospects_after_dedupe = dedupe_stats['unique_prospects_after_merge']

            print(f"✅ Deduplication complete: {job.stats.raw_prospects_found} → {job.stats.prospects_after_dedupe} unique prospects")

        # Calculate final job statistics
        self._update_final_job_stats(job)

        # Print prospects summary at the end
        self.print_prospects_summary()

        # Export split CSVs if directory is provided and we're not in URL print-only mode
        if self.output_dir:
            exported_files = self.export_attio_csvs(self.output_dir)
            for file_type, file_path in exported_files.items():
                job.output_files[file_type] = file_path

        # Save main prospects file if output path specified
        if self.output_path:
            job.output_files['prospects_csv'] = self.output_path

        # End job and print summary
        completed_job = self.job_tracker.end_job(success=True)
        print("\n" + "="*80)
        print(self.job_tracker.get_job_summary())
        print("="*80)

    def _update_final_job_stats(self, job):
        """Update final job statistics after processing"""
        prospects = self.all_prospects

        # Basic counts
        job.stats.prospects_after_dedupe = len(prospects)
        job.stats.contactable_prospects = sum(1 for p in prospects if p.contactability_score and p.contactability_score >= 50)
        job.stats.maintainer_prospects = sum(1 for p in prospects if p.is_maintainer)
        job.stats.org_member_prospects = sum(1 for p in prospects if p.is_org_member)

        # Tier distribution
        tier_counts = {'A': 0, 'B': 0, 'C': 0, 'REJECT': 0}
        for prospect in prospects:
            tier = getattr(prospect, 'prospect_tier', 'unknown')
            if tier in tier_counts:
                tier_counts[tier] += 1
        job.stats.prospects_by_tier = tier_counts

    def export_csv(self, output_path: str):
        """Export prospects to CSV"""
        if not self.all_prospects:
            return
            
        # Use same fieldnames as init_csv_file
        fieldnames = [
            # Core identification
            'lead_id', 'login', 'id', 'node_id',
            # Personal info
            'name', 'company', 'email_public_commit', 'email_profile',
            'location', 'bio', 'pronouns',
            # Repository context
            'repo_full_name', 'repo_description', 'signal', 'signal_type',
            'signal_at', 'topics', 'language', 'stars', 'forks', 'watchers',
            # Maintainer status
            'is_maintainer', 'is_org_member', 'is_codeowner', 'permission_level', 'commit_count_90d',
            # Contact enrichment
            'contactability_score', 'email_type', 'is_disposable_email', 'corporate_domain', 'linkedin_query',
            # URLs
            'github_user_url', 'github_repo_url', 'avatar_url', 'html_url',
            'api_url', 'followers_url', 'following_url', 'gists_url',
            'starred_url', 'subscriptions_url', 'organizations_url',
            'repos_url', 'events_url', 'received_events_url',
            # Social/Professional
            'twitter_username', 'blog', 'linkedin_username', 'hireable',
            # GitHub Statistics
            'public_repos', 'public_gists', 'followers', 'following',
            'total_private_repos', 'owned_private_repos', 'private_gists',
            'disk_usage', 'collaborators',
            # Contribution data
            'contributions_last_year', 'total_contributions',
            'longest_streak', 'current_streak',
            # Account metadata
            'created_at', 'updated_at', 'type', 'site_admin',
            'gravatar_id', 'suspended_at',
            # Plan information
            'plan_name', 'plan_space', 'plan_collaborators', 'plan_private_repos',
            # Scoring and tiering
            'prospect_score', 'prospect_tier', 'scoring_components', 'risk_factors', 'priority_signals', 'cohort',
            # Compliance
            'compliance_risk_level', 'compliance_blocked', 'compliance_risk_factors', 'geo_location',
            # Additional flags
            'two_factor_authentication', 'has_organization_projects',
            'has_repository_projects'
        ]
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for prospect in self.all_prospects:
                writer.writerow(prospect.to_dict())

    def export_attio_csvs(self, output_dir: str) -> Dict[str, str]:
        """Export People, Repos, Membership, and Signals CSVs matching Attio headers.
        Returns dict of file_type -> file_path mappings.
        """
        os.makedirs(output_dir or '.', exist_ok=True)
        # Each object into its own folder under the provided output_dir
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        attio_dir = os.path.join(output_dir, f"export_{timestamp}")
        os.makedirs(attio_dir, exist_ok=True)
        people_dir = os.path.join(attio_dir, 'People')
        repos_dir = os.path.join(attio_dir, 'Repos')
        memberships_dir = os.path.join(attio_dir, 'Memberships')
        signals_dir = os.path.join(attio_dir, 'Signals')
        for d in [people_dir, repos_dir, memberships_dir, signals_dir]:
            os.makedirs(d, exist_ok=True)
        # People.csv (attach repo_membership_* fields)
        people_headers = [
            'login','id','node_id','lead_id','name','company_raw','company_domain','email_addresses','email_public_commit',
            'Predicted Email','location','bio','pronouns','public_repos','public_gists','followers','following',
            'repo_full_name','repo_name','repo_owner_login','repo_description','repo_topics','repo_primary_language',
            'repo_stars','repo_forks','repo_watchers','repo_open_issues','repo_is_fork','repo_is_archived',
            'repo_created_at','repo_updated_at','repo_pushed_at','repo_html_url',
            'created_at','updated_at','html_url','avatar_url','github_user_url','api_url'
        ]
        with open(os.path.join(people_dir, 'People.csv'), 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=people_headers)
            w.writeheader()
            for row in self.people_records.values():
                best_email = row.get('email_profile') or row.get('email_public_commit') or row.get('Predicted Email')
                out = {
                    'login': row.get('login'),
                    'id': row.get('id'),
                    'node_id': row.get('node_id'),
                    'lead_id': row.get('lead_id'),
                    'name': row.get('name'),
                    'company_raw': row.get('company'),
                    'company_domain': row.get('company_domain'),
                    'email_addresses': best_email,
                    'email_public_commit': row.get('email_public_commit'),
                    'Predicted Email': row.get('Predicted Email'),
                    'location': row.get('location'),
                    'bio': row.get('bio'),
                    'pronouns': row.get('pronouns'),
                    'public_repos': row.get('public_repos'),
                    'public_gists': row.get('public_gists'),
                    'followers': row.get('followers'),
                    'following': row.get('following'),
                    'repo_full_name': row.get('repo_full_name'),
                    'repo_name': row.get('repo_name'),
                    'repo_owner_login': row.get('repo_owner_login'),
                    'repo_description': row.get('repo_description'),
                    'repo_topics': row.get('repo_topics'),
                    'repo_primary_language': row.get('repo_primary_language'),
                    'repo_stars': row.get('repo_stars'),
                    'repo_forks': row.get('repo_forks'),
                    'repo_watchers': row.get('repo_watchers'),
                    'repo_open_issues': row.get('repo_open_issues'),
                    'repo_is_fork': row.get('repo_is_fork'),
                    'repo_is_archived': row.get('repo_is_archived'),
                    'repo_created_at': row.get('repo_created_at'),
                    'repo_updated_at': row.get('repo_updated_at'),
                    'repo_pushed_at': row.get('repo_pushed_at'),
                    'repo_html_url': row.get('repo_html_url'),
                    'created_at': row.get('created_at'),
                    'updated_at': row.get('updated_at'),
                    'html_url': row.get('html_url'),
                    'avatar_url': row.get('avatar_url'),
                    'github_user_url': row.get('github_user_url'),
                    'api_url': row.get('api_url'),
                }
                w.writerow(out)
        
        # Repos.csv
        repo_headers = [
            'repo_full_name','repo_name','owner_login','host','description','primary_language','license','topics',
            'stars','forks','watchers','open_issues','is_fork','is_archived','created_at','updated_at','pushed_at',
            'html_url','api_url','recent_push_30d'
        ]
        with open(os.path.join(repos_dir, 'Repos.csv'), 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=repo_headers)
            w.writeheader()
            for row in self.repo_records.values():
                w.writerow({k: row.get(k) for k in repo_headers})
        
        # Membership.csv
        membership_headers = [
            'membership_id','login','repo_full_name','role','permission','contributions_past_year','last_activity_at'
        ]
        with open(os.path.join(memberships_dir, 'Membership.csv'), 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=membership_headers)
            w.writeheader()
            for row in self.membership_records.values():
                out_row = {
                    'membership_id': row.get('membership_id'),
                    'login': row.get('login'),
                    'repo_full_name': row.get('repo_full_name'),
                    'role': row.get('role'),
                    'permission': row.get('permission'),
                    'contributions_past_year': row.get('contributions_past_year'),
                    'last_activity_at': row.get('last_activity_at'),
                }
                w.writerow(out_row)
        
        # Signals.csv
        signal_headers = ['signal_id','login','repo_full_name','signal_type','signal','signal_at','url','source']
        signals_file = os.path.join(signals_dir, 'Signals.csv')
        with open(signals_file, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=signal_headers)
            w.writeheader()
            for row in self.signal_records.values():
                out_row = {k: row.get(k) for k in signal_headers}
                w.writerow(out_row)

        # Return file paths for job tracking
        return {
            'people_csv': os.path.join(people_dir, 'People.csv'),
            'repos_csv': os.path.join(repos_dir, 'Repos.csv'),
            'memberships_csv': os.path.join(memberships_dir, 'Membership.csv'),
            'signals_csv': signals_file,
            'export_dir': attio_dir
        }

    def export_attio_csvs_flat(self, attio_dir: str):
        """Export Attio CSVs directly into the provided directory (no subfolders)."""
        os.makedirs(attio_dir or '.', exist_ok=True)
        # Use the same accumulators as export_attio_csvs
        # People.csv
        people_headers = [
            'login','id','node_id','lead_id','name','company_raw','email_addresses','email_public_commit',
            'Predicted Email','location','bio','pronouns','public_repos','public_gists','followers','following',
            'repo_full_name','repo_name','repo_owner_login','repo_description','repo_topics','repo_primary_language',
            'repo_stars','repo_forks','repo_watchers','repo_open_issues','repo_is_fork','repo_is_archived',
            'repo_created_at','repo_updated_at','repo_pushed_at','repo_html_url',
            'created_at','updated_at','html_url','avatar_url','github_user_url','api_url'
        ]
        with open(os.path.join(attio_dir, 'People.csv'), 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=people_headers)
            w.writeheader()
            for row in self.people_records.values():
                best_email = row.get('email_profile') or row.get('email_public_commit') or row.get('Predicted Email')
                out = {
                    'login': row.get('login'),
                    'id': row.get('id'),
                    'node_id': row.get('node_id'),
                    'lead_id': row.get('lead_id'),
                    'name': row.get('name'),
                    'company_raw': row.get('company'),
                    'email_addresses': best_email,
                    'email_public_commit': row.get('email_public_commit'),
                    'Predicted Email': row.get('Predicted Email'),
                    'location': row.get('location'),
                    'bio': row.get('bio'),
                    'pronouns': row.get('pronouns'),
                    'public_repos': row.get('public_repos'),
                    'public_gists': row.get('public_gists'),
                    'followers': row.get('followers'),
                    'following': row.get('following'),
                    'repo_full_name': row.get('repo_full_name'),
                    'repo_name': row.get('repo_name'),
                    'repo_owner_login': row.get('repo_owner_login'),
                    'repo_description': row.get('repo_description'),
                    'repo_topics': row.get('repo_topics'),
                    'repo_primary_language': row.get('repo_primary_language'),
                    'repo_stars': row.get('repo_stars'),
                    'repo_forks': row.get('repo_forks'),
                    'repo_watchers': row.get('repo_watchers'),
                    'repo_open_issues': row.get('repo_open_issues'),
                    'repo_is_fork': row.get('repo_is_fork'),
                    'repo_is_archived': row.get('repo_is_archived'),
                    'repo_created_at': row.get('repo_created_at'),
                    'repo_updated_at': row.get('repo_updated_at'),
                    'repo_pushed_at': row.get('repo_pushed_at'),
                    'repo_html_url': row.get('repo_html_url'),
                    'created_at': row.get('created_at'),
                    'updated_at': row.get('updated_at'),
                    'html_url': row.get('html_url'),
                    'avatar_url': row.get('avatar_url'),
                    'github_user_url': row.get('github_user_url'),
                    'api_url': row.get('api_url'),
                }
                w.writerow(out)
        # Repos.csv
        repo_headers = [
            'repo_full_name','repo_name','owner_login','host','description','primary_language','license','topics',
            'stars','forks','watchers','open_issues','is_fork','is_archived','created_at','updated_at','pushed_at',
            'html_url','api_url','recent_push_30d'
        ]
        with open(os.path.join(attio_dir, 'Repos.csv'), 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=repo_headers)
            w.writeheader()
            for row in self.repo_records.values():
                w.writerow({k: row.get(k) for k in repo_headers})
        # Membership.csv
        membership_headers = [
            'membership_id','login','repo_full_name','role','permission','contributions_past_year','last_activity_at'
        ]
        with open(os.path.join(attio_dir, 'Membership.csv'), 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=membership_headers)
            w.writeheader()
            for row in self.membership_records.values():
                w.writerow({k: row.get(k) for k in membership_headers})
        # Signals.csv
        signal_headers = ['signal_id','login','repo_full_name','signal_type','signal','signal_at','url','source']
        with open(os.path.join(attio_dir, 'Signals.csv'), 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=signal_headers)
            w.writeheader()
            for row in self.signal_records.values():
                w.writerow({k: row.get(k) for k in signal_headers})

def main():
    parser = argparse.ArgumentParser(description='GitHub Prospect Scraper')
    parser.add_argument('--config', default='config.yaml', help='Config file path')
    parser.add_argument('--out', default='data/prospects.csv', help='Output CSV path')
    parser.add_argument('--out-dir', default='data', help='Directory to write split Attio CSVs (people/repos/memberships/signals)')
    parser.add_argument('-n', '--max-repos', type=int, help='Maximum number of repos to process (overrides config)')
    parser.add_argument('--repos', type=int, help='Alias for --max-repos (overrides config.limits.max_repos)')
    parser.add_argument('--leads', type=int, help='Maximum number of people/leads (with email) to collect (overrides config.limits.max_people)')
    parser.add_argument('--url', help='GitHub URL to scrape (user profile or repository)')
    parser.add_argument('--print-only', action='store_true', help='Only print results, do not save to CSV')
    parser.add_argument('--run-all-segments', action='store_true', help='Run all queries in config.target_segments and combine results')
    parser.add_argument('--dedup-db', default=os.environ.get('DEDUP_DB', 'data/dedup.db'), help='Path to SQLite DB for dedup (default: $DEDUP_DB or data/dedup.db)')
    parser.add_argument('--no-dedup', action='store_true', help='Disable deduplication (process all logins)')
    parser.add_argument('--timeout-secs', type=int, default=int(os.environ.get('HTTP_TIMEOUT_SECS', '15')), help='HTTP request timeout seconds (default: $HTTP_TIMEOUT_SECS or 15)')
    args = parser.parse_args()
    
    # Check for GitHub token
    # Prefer token from config.github.token_env, then GITHUB_TOKEN, then GH_TOKEN
    token_env_name = None
    try:
        with open(args.config, 'r') as _cf:
            _cfg_for_token = yaml.safe_load(_cf) or {}
            token_env_name = (((_cfg_for_token.get('github') or {}).get('token_env')) or None)
    except Exception:
        token_env_name = None
    token = None
    if token_env_name:
        token = os.environ.get(token_env_name)
    if not token:
        # Get token from environment
        token = os.environ.get('GITHUB_TOKEN', '')
        if not token:
            print("❌ Error: GITHUB_TOKEN environment variable not set")
            print("Please run: export GITHUB_TOKEN=your_token_here")
            sys.exit(1)
    # Sanitize
    if token:
        token = token.strip().strip('"').strip("'")
    if not token:
        print("⚠️  Warning: GITHUB_TOKEN environment variable not set")
        print("   Running without authentication (limited to public data)")
        print("   Get a token at: https://github.com/settings/tokens for full access")
        token = ""
    
    # Handle URL mode
    if args.url:
        
        # Use minimal config for URL mode
        config = {
            'filters': {'activity_days': 90},
            'limits': {'per_repo_prs': 10, 'per_repo_commits': 10, 'max_people': 50},
            'delay': 1,
            'dedup': {'enabled': (not args.no_dedup), 'db_path': args.dedup_db}
        }
        # HTTP timeout
        config['http'] = {'timeout_secs': args.timeout_secs}
        # Apply overrides in URL mode
        if args.max_repos or args.repos:
            config['limits']['max_repos'] = args.repos or args.max_repos
            print(f"🔧 Overriding max_repos to {config['limits']['max_repos']}")
        if args.leads:
            config['limits']['max_people'] = args.leads
            print(f"🔧 Overriding max_people to {config['limits']['max_people']}")
            if not (args.max_repos or args.repos):
                desired = min(200, max(50, config['limits']['max_people'] * 50))
                current = config['limits'].get('max_repos', 0) or 0
                config['limits']['max_repos'] = max(current, desired)
                print(f"🔧 Auto-setting max_repos to {config['limits']['max_repos']} for leads target {config['limits']['max_people']}")
        
        # Don't save to CSV if print-only mode
        output_path = None if args.print_only else args.out
        if output_path:
            os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        
        scraper = GitHubScraper(token, config, output_path, None)
        
        # Initialize CSV if needed
        if output_path:
            scraper._init_csv_file()
        
        # Scrape from URL
        scraper.scrape_from_url(args.url)
        
        # Always print results in URL mode
        scraper.print_prospects_summary()
        
        # Close CSV file and dedup DB
        if output_path:
            scraper._close_csv_file()
        else:
            # Ensure dedup DB closed even if no CSV
            scraper._close_csv_file()
        
        return
        
    # Regular config-based mode
    try:
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
            
        # Overrides from CLI
        if args.max_repos or args.repos:
            config['limits']['max_repos'] = args.repos or args.max_repos
            print(f"🔧 Overriding max_repos to {config['limits']['max_repos']}")
        if args.leads:
            config['limits']['max_people'] = args.leads
            print(f"🔧 Overriding max_people to {config['limits']['max_people']}")
            if not (args.max_repos or args.repos):
                desired = min(200, max(50, config['limits']['max_people'] * 50))
                current = config['limits'].get('max_repos', 0) or 0
                config['limits']['max_repos'] = max(current, desired)
                print(f"🔧 Auto-setting max_repos to {config['limits']['max_repos']} for leads target {config['limits']['max_people']}")
        # Inject dedup configuration
        config.setdefault('dedup', {})
        config['dedup']['enabled'] = (not args.no_dedup)
        config['dedup']['db_path'] = args.dedup_db
        # Inject HTTP timeout
        config.setdefault('http', {})
        config['http']['timeout_secs'] = args.timeout_secs
    except FileNotFoundError:
        print(f"❌ Error: Config file '{args.config}' not found")
        print("Creating default config...")
        
        # Create default config
        default_config = {
            'search': {
                'query': 'language:python stars:>100 pushed:>2024-01-01',
                'sort': 'updated',
                'order': 'desc',
                'per_page': 30
            },
            'filters': {
                'activity_days': 90
            },
            'limits': {
                'max_repos': 10,
                'per_repo_prs': 5,
                'per_repo_commits': 5,
                'max_people': 100
            },
            'delay': 1,
            'dedup': {'enabled': (not args.no_dedup), 'db_path': args.dedup_db},
            'http': {'timeout_secs': args.timeout_secs}
        }
        
        os.makedirs(os.path.dirname(args.config) or '.', exist_ok=True)
        with open(args.config, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False)
            
        print(f"✅ Created default config at {args.config}")
        print("Edit it and run again!")
        sys.exit(0)
        
    # Create output directories
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    os.makedirs(args.out_dir or 'data', exist_ok=True)

    # Multi-segment mode
    if args.run_all_segments and config.get('target_segments'):
        combined = []
        seen_ids: Set[str] = set()
        base_config = copy.deepcopy(config)
        for segment in config['target_segments']:
            q = segment.get('query')
            if not q:
                continue
            seg_config = copy.deepcopy(base_config)
            seg_config.setdefault('search', {})['query'] = q
            scraper = GitHubScraper(token, seg_config, None, args.out_dir)
            scraper.scrape()
            for p in scraper.all_prospects:
                if p.lead_id in seen_ids:
                    continue
                seen_ids.add(p.lead_id)
                combined.append(p)
            # Close dedup DB between segments
            scraper._close_csv_file()
        # Write combined CSVs
        if args.out:
            fieldnames = list(combined[0].to_dict().keys()) if combined else []
            with open(args.out, 'w', newline='', encoding='utf-8') as f:
                if fieldnames:
                    w = csv.DictWriter(f, fieldnames=fieldnames)
                    w.writeheader()
                    for p in combined:
                        w.writerow(p.to_dict())
        # Export Attio splits from merged accumulators is non-trivial; just from last segment export
        # Alternatively we could merge accumulators across segments; for now we skip.
        print(f"✅ Collected {len(seen_ids)} prospects across {len(config['target_segments'])} segments")
        return

    # Single-query mode
    scraper = GitHubScraper(token, config, args.out, args.out_dir)
    scraper.scrape()

    scraper._close_csv_file()

    if not scraper.csv_initialized and args.out:
        scraper.export_csv(args.out)


if __name__ == '__main__':
    import signal
    import sys
    
    def signal_handler(sig, frame):
        print('\n\n⚠️  Interrupted by user (Ctrl+C)')
        print('📊 Saving current progress...')
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⚠️  Interrupted by user (Ctrl+C)')
        print('📊 Saving current progress...')
        sys.exit(0)
