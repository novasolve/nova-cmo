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
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import copy
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import yaml
import argparse
from dataclasses import dataclass, asdict
from urllib.parse import urlparse
from tqdm import tqdm


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
    signal_type: str  # 'pr' or 'commit'
    signal_at: str
    topics: str
    language: str
    stars: int
    forks: Optional[int]
    watchers: Optional[int]
    
    # URLs
    github_user_url: str
    github_repo_url: str
    avatar_url: Optional[str]
    html_url: Optional[str]
    api_url: Optional[str]
    followers_url: Optional[str]
    following_url: Optional[str]
    gists_url: Optional[str]
    starred_url: Optional[str]
    subscriptions_url: Optional[str]
    organizations_url: Optional[str]
    repos_url: Optional[str]
    events_url: Optional[str]
    received_events_url: Optional[str]
    
    # Social/Professional
    twitter_username: Optional[str]
    blog: Optional[str]
    linkedin_username: Optional[str]  # Extracted from blog if linkedin URL
    hireable: Optional[bool]
    
    # GitHub Statistics
    public_repos: Optional[int]
    public_gists: Optional[int]
    followers: Optional[int]
    following: Optional[int]
    total_private_repos: Optional[int]
    owned_private_repos: Optional[int]
    private_gists: Optional[int]
    disk_usage: Optional[int]
    collaborators: Optional[int]
    
    # Contribution data (requires additional API calls)
    contributions_last_year: Optional[int]
    total_contributions: Optional[int]
    longest_streak: Optional[int]
    current_streak: Optional[int]
    
    # Account metadata
    created_at: Optional[str]
    updated_at: Optional[str]
    type: Optional[str]  # User type
    site_admin: Optional[bool]
    gravatar_id: Optional[str]
    suspended_at: Optional[str]
    
    # Plan information
    plan_name: Optional[str]
    plan_space: Optional[int]
    plan_collaborators: Optional[int]
    plan_private_repos: Optional[int]
    
    # Additional flags
    two_factor_authentication: Optional[bool]
    has_organization_projects: Optional[bool]
    has_repository_projects: Optional[bool]
    
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


class GitHubScraper:
    """Scrapes GitHub for prospect data"""
    
    def __init__(self, token: str, config: dict, output_path: str = None, output_dir: Optional[str] = None):
        self.token = token
        self.config = config
        self.output_path = output_path
        self.output_dir = output_dir
        self.session = self._create_session()
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'leads-scraper/1.0'
        }
        # Only add auth header if token is provided and valid
        if token and token.strip():
            # Prefer Bearer for fine-grained and classic tokens; GitHub supports both
            self.headers['Authorization'] = f'Bearer {token}'
        self.prospects: Set[str] = set()  # Track unique lead_ids
        self.all_prospects: List[Prospect] = []
        self.csv_file = None
        self.csv_writer = None
        self.csv_initialized = False
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
        
    def _create_session(self):
        """Create session with retry logic"""
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.3,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session
        
    def _rate_limit_wait(self, response):
        """Handle GitHub rate limiting"""
        if response.status_code == 403:
            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
            if reset_time:
                wait_time = reset_time - int(time.time()) + 5
                if wait_time > 0:
                    print(f"Rate limited. Waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    return True
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
        
    def search_repos(self) -> List[Dict]:
        """Search GitHub repos based on config criteria"""
        repos = []
        query = self.config['search']['query']
        sort = self.config['search'].get('sort', 'updated')
        order = self.config['search'].get('order', 'desc')
        per_page = min(self.config['search'].get('per_page', 30), 100)
        max_repos = self.config['limits']['max_repos']
        
        page = 1
        while len(repos) < max_repos:
            url = f"https://api.github.com/search/repositories"
            params = {
                'q': query,
                'sort': sort,
                'order': order,
                'per_page': per_page,
                'page': page
            }
            
            response = self.session.get(url, headers=self.headers, params=params, timeout=10)
            
            if self._rate_limit_wait(response):
                continue
                
            if response.status_code != 200:
                try:
                    err = response.json()
                except Exception:
                    err = {}
                message = (err.get('message') or '')
                print(f"Error searching repos: {response.status_code} {message}")
                # Fallback: if 422 (Validation Failed), try to simplify query by splitting on OR and running first part
                if response.status_code == 422 and 'q' in params and ' OR ' in params['q']:
                    simple_q = params['q'].split(' OR ')[0]
                    params['q'] = simple_q
                    response = self.session.get(url, headers=self.headers, params=params, timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        repos.extend(data.get('items', []))
                        if len(data.get('items', [])) < per_page:
                            break
                        page += 1
                        time.sleep(self.config.get('delay', 1))
                        continue
                break
                
            data = response.json()
            repos.extend(data.get('items', []))
            
            if len(data.get('items', [])) < per_page:
                break
                
            page += 1
            time.sleep(self.config.get('delay', 1))  # Be nice to GitHub
            
        return repos[:max_repos]
        
    def get_pr_authors(self, repo: Dict) -> List[Dict]:
        """Get recent PR authors for a repo"""
        pr_authors = []
        owner = repo['owner']['login']
        repo_name = repo['name']
        
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
        owner = repo['owner']['login']
        repo_name = repo['name']
        
        # Calculate date range
        days_back = self.config['filters'].get('activity_days', 90)
        since = (datetime.now() - timedelta(days=days_back)).isoformat()
        
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
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "User-Agent": "github-prospect-scraper/1.1"
        }
        try:
            resp = requests.post("https://api.github.com/graphql", json={"query": query, "variables": variables}, headers=headers, timeout=20)
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
    
    def parse_github_url(self, url: str) -> Dict:
        """Parse GitHub URL to extract user/repo information"""
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
        user = author_data['user']
        
        # Generate stable lead_id
        lead_id = hashlib.md5(f"{user['login']}_{repo['full_name']}".encode()).hexdigest()[:12]
        
        # Skip if we've already seen this lead
        if lead_id in self.prospects:
            return None
            
        # Get full user details
        user_details = self.get_user_details(user['login'])
        
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
        
        # Extract pronouns (often in bio or name field)
        pronouns = None
        if user_details.get('bio'):
            bio_lower = user_details['bio'].lower()
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
            stars=repo.get('stargazers_count', 0),
            forks=repo.get('forks_count'),
            watchers=repo.get('watchers_count'),
            
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
        
        # Write to CSV immediately if incremental writing is enabled
        if self.output_path:
            self._write_prospect_to_csv(prospect)
        
        # Build Attio object rows
        self._upsert_person_record(user_details, user['login'], email_commit, repo)
        self._upsert_repo_record(repo)
        self._add_membership_record(user['login'], repo, author_data.get('signal_at'))
        self._add_signal_record(user['login'], repo, author_data)
            
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
            'company_domain': company_domain,
            'Predicted Email': '',
            'location': user_details.get('location'),
            'bio': user_details.get('bio'),
            'pronouns': pronouns,
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
        full_name = repo['full_name']
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
            'stars': repo.get('stargazers_count', 0),
            'watchers': repo.get('watchers_count', 0),
            'subscribers': details.get('subscribers_count'),
            'forks': repo.get('forks_count'),
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
        repo_full_name = repo['full_name']
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
        repo_full_name = repo['full_name']
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
            'source': 'GitHub'
        }
        
    def scrape(self):
        """Main scraping logic"""
        # Initialize CSV file for incremental writing
        if self.output_path:
            self._init_csv_file()
            
        repos = self.search_repos()
        
        # Use tqdm for progress tracking
        repo_pbar = tqdm(repos, desc="Processing repos", unit="repo")
        
        for repo in repo_pbar:
            repo_pbar.set_description(f"Processing {repo['full_name']}")
            
            # Get PR authors
            if self.config['limits']['per_repo_prs'] > 0:
                pr_authors = self.get_pr_authors(repo)
                
                if pr_authors:
                    pr_pbar = tqdm(pr_authors, desc="  PR authors", unit="author", leave=False)
                    for author_data in pr_pbar:
                        prospect = self.create_prospect(author_data, repo)
                        if prospect:
                            self.all_prospects.append(prospect)
                            pr_pbar.set_description(f"  Added {prospect.login}")
                        
            # Get commit authors
            if self.config['limits']['per_repo_commits'] > 0:
                commit_authors = self.get_commit_authors(repo)
                
                if commit_authors:
                    commit_pbar = tqdm(commit_authors, desc="  Commit authors", unit="author", leave=False)
                    for author_data in commit_pbar:
                        prospect = self.create_prospect(author_data, repo)
                        if prospect:
                            self.all_prospects.append(prospect)
                            commit_pbar.set_description(f"  Added {prospect.login}")
                        
            # Update main progress bar with current stats
            repo_pbar.set_postfix(prospects=len(self.all_prospects))
                        
            # Check if we've hit our people limit
            if len(self.all_prospects) >= self.config['limits']['max_people']:
                repo_pbar.set_description(f"Reached max people limit ({self.config['limits']['max_people']})")
                break
                
            # Be nice to GitHub
            time.sleep(self.config.get('delay', 1))
        
        repo_pbar.close()
        
        # Print prospects summary at the end
        self.print_prospects_summary()
        
        # Export split CSVs if directory is provided and we're not in URL print-only mode
        if self.output_dir:
            self.export_attio_csvs(self.output_dir)
        
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
            # Additional flags
            'two_factor_authentication', 'has_organization_projects', 
            'has_repository_projects'
        ]
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for prospect in self.all_prospects:
                writer.writerow(prospect.to_dict())

    def export_attio_csvs(self, output_dir: str):
        """Export People, Repos, Membership, and Signals CSVs matching Attio headers."""
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
        # People.csv
        people_headers = [
            'login','id','node_id','lead_id','name','company','email_profile','email_public_commit',
            'Predicted Email','location','bio','pronouns','public_repos','public_gists','followers','following',
            'created_at','updated_at','html_url','avatar_url','github_user_url','api_url'
        ]
        with open(os.path.join(people_dir, 'People.csv'), 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=people_headers)
            w.writeheader()
            for row in self.people_records.values():
                # ensure all keys exist
                w.writerow({k: row.get(k) for k in people_headers})
        
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
        with open(os.path.join(signals_dir, 'Signals.csv'), 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=signal_headers)
            w.writeheader()
            for row in self.signal_records.values():
                out_row = {k: row.get(k) for k in signal_headers}
                w.writerow(out_row)

    def export_attio_csvs_flat(self, attio_dir: str):
        """Export Attio CSVs directly into the provided directory (no subfolders)."""
        os.makedirs(attio_dir or '.', exist_ok=True)
        # Use the same accumulators as export_attio_csvs
        # People.csv
        people_headers = [
            'login','id','node_id','lead_id','name','company','email_profile','email_public_commit',
            'Predicted Email','location','bio','pronouns','public_repos','public_gists','followers','following',
            'created_at','updated_at','html_url','avatar_url','github_user_url','api_url'
        ]
        with open(os.path.join(attio_dir, 'People.csv'), 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=people_headers)
            w.writeheader()
            for row in self.people_records.values():
                w.writerow({k: row.get(k) for k in people_headers})
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
    parser.add_argument('--leads', type=int, help='Maximum number of people/leads to collect (overrides config.limits.max_people)')
    parser.add_argument('--url', help='GitHub URL to scrape (user profile or repository)')
    parser.add_argument('--print-only', action='store_true', help='Only print results, do not save to CSV')
    parser.add_argument('--run-all-segments', action='store_true', help='Run all queries in config.target_segments and combine results')
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
        token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
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
            'delay': 1
        }
        # Apply overrides in URL mode as well
        if args.max_repos or args.repos:
            config['limits']['max_repos'] = args.repos or args.max_repos
            print(f"🔧 Overriding max_repos to {config['limits']['max_repos']}")
        if args.leads:
            config['limits']['max_people'] = args.leads
            print(f"🔧 Overriding max_people to {config['limits']['max_people']}")
        
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
        
        # Close CSV file
        if output_path:
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
            'delay': 1
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
    main()
