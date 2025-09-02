#!/usr/bin/env python3
"""
GitHub CI/Workflow Scraper for Bottom-up Lead Discovery

This scraper implements the bottom-up approach:
1. Search GitHub for Python repos with real CI activity
2. Extract workflow file authors (commits to .github/workflows/** last 90 days)
3. Extract top committers to tests/**
4. Parse CODEOWNERS for .github/workflows and tests/** ownership
5. Map GitHub handles to LinkedIn/Company via metadata

Focus: Directors (deciders) and Maintainers (practitioners who own CI)
"""

import os
import sys
import csv
import time
import json
import hashlib
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import yaml
import argparse
from dataclasses import dataclass, asdict
from urllib.parse import urlparse
from tqdm import tqdm
import base64
from collections import defaultdict, Counter


@dataclass
class CILead:
    """Represents a CI/DevOps lead with workflow and testing context"""
    # Identity (required fields first)
    lead_id: str  # Unique hash
    login: str
    github_id: int
    repo_full_name: str
    signal_type: str  # workflow_author, test_committer, codeowner, maintainer
    role_type: str  # director, maintainer, contributor
    
    # Identity (optional)
    name: Optional[str] = None
    
    # Contact & Company
    email: Optional[str] = None
    company: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None
    
    # Repository Context
    repo_description: Optional[str] = None
    repo_stars: int = 0
    repo_language: Optional[str] = None
    repo_topics: str = ""
    
    # CI/DevOps Signals
    workflow_files_authored: int = 0  # Number of workflow files they've committed to
    test_commits_90d: int = 0  # Commits to tests/** in last 90 days
    workflow_commits_90d: int = 0  # Commits to .github/workflows/** in last 90 days
    codeowner_patterns: str = ""  # What they own according to CODEOWNERS
    
    # Role Classification
    is_org_member: bool = False
    permission_level: Optional[str] = None  # admin, maintain, write, read
    
    # Activity Metrics
    followers: int = 0
    public_repos: int = 0
    contributions_last_year: int = 0
    account_created: Optional[str] = None
    last_activity: Optional[str] = None
    
    # Scoring
    ci_expertise_score: int = 0  # 0-100 based on CI/DevOps activity
    decision_maker_score: int = 0  # 0-100 likelihood of being a decision maker
    overall_score: int = 0
    tier: str = "C"  # A, B, C
    
    def to_dict(self):
        return asdict(self)


class GitHubCIScraper:
    """Scraper focused on CI/DevOps practitioners and decision makers"""
    
    def __init__(self, token: str, config: dict, output_path: str = None):
        self.token = token
        self.config = config
        self.output_path = output_path
        self.session = self._create_session()
        self.headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'ci-leads-scraper/1.0'
        }
        if token and token.strip():
            self.headers['Authorization'] = self._get_auth_header(token)
        
        self.leads: Set[str] = set()  # Track unique lead IDs
        self.all_leads: List[CILead] = []
        self.csv_file = None
        self.csv_writer = None
        self.csv_initialized = False
        
        # CI-specific search queries
        self.ci_search_queries = [
            'path:.github/workflows language:YAML pytest pushed:>=2024-06-01',
            'path:.github/workflows language:YAML "pytest -q" pushed:>=2024-06-01', 
            'path:.github/workflows language:YAML tox pushed:>=2024-06-01',
            'filename:CODEOWNERS ".github/workflows"',
            'filename:CODEOWNERS "tests/"'
        ]
    
    def _get_auth_header(self, token: str) -> str:
        """Get the appropriate authorization header"""
        token = token.strip()
        if token.startswith('ghp_'):
            return f'token {token}'
        elif token.startswith('github_token_'):
            return f'Bearer {token}'
        else:
            return f'Bearer {token}'
    
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
                    print(f"⏳ Rate limited. Waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                    return True
        return False
    
    def search_ci_repositories(self) -> List[Dict]:
        """Search for repositories with CI activity using multiple strategies"""
        all_repos = []
        seen_repos = set()
        
        print("🔍 Searching for Python repos with CI activity...")
        
        for query in self.ci_search_queries:
            print(f"   Query: {query}")
            repos = self._search_repos_by_query(query)
            
            for repo in repos:
                repo_id = repo.get('full_name')
                if repo_id and repo_id not in seen_repos:
                    all_repos.append(repo)
                    seen_repos.add(repo_id)
            
            time.sleep(1)  # Be nice to GitHub
        
        # Sort by stars and recent activity
        all_repos.sort(key=lambda r: (r.get('stargazers_count', 0), r.get('pushed_at', '')), reverse=True)
        
        # Limit results
        max_repos = self.config.get('limits', {}).get('max_repos', 100)
        return all_repos[:max_repos]
    
    def _search_repos_by_query(self, query: str) -> List[Dict]:
        """Search repositories by a specific query"""
        repos = []
        page = 1
        per_page = 30
        
        while len(repos) < 200:  # Reasonable limit per query
            url = "https://api.github.com/search/repositories"
            params = {
                'q': query,
                'sort': 'updated',
                'order': 'desc',
                'per_page': per_page,
                'page': page
            }
            
            response = self.session.get(url, headers=self.headers, params=params, timeout=10)
            
            if self._rate_limit_wait(response):
                continue
            
            if response.status_code != 200:
                print(f"❌ Search error: {response.status_code}")
                break
            
            data = response.json()
            items = data.get('items', [])
            
            if not items:
                break
                
            repos.extend(items)
            
            if len(items) < per_page:
                break
                
            page += 1
            time.sleep(0.5)
        
        return repos
    
    def extract_workflow_authors(self, repo_full_name: str) -> List[Tuple[str, int]]:
        """Extract authors of .github/workflows files in last 90 days"""
        authors = defaultdict(int)
        
        try:
            # Get commits to .github/workflows path in last 90 days
            since_date = (datetime.now() - timedelta(days=90)).isoformat()
            
            url = f"https://api.github.com/repos/{repo_full_name}/commits"
            params = {
                'path': '.github/workflows',
                'since': since_date,
                'per_page': 100
            }
            
            response = self.session.get(url, headers=self.headers, params=params, timeout=10)
            
            if self._rate_limit_wait(response):
                response = self.session.get(url, headers=self.headers, params=params, timeout=10)
            
            if response.status_code == 200:
                commits = response.json()
                for commit in commits:
                    author = commit.get('author', {})
                    if author and author.get('login'):
                        authors[author['login']] += 1
        
        except Exception as e:
            print(f"⚠️  Error extracting workflow authors for {repo_full_name}: {e}")
        
        return list(authors.items())
    
    def extract_test_committers(self, repo_full_name: str) -> List[Tuple[str, int]]:
        """Extract top committers to tests/** directories in last 90 days"""
        committers = defaultdict(int)
        
        try:
            # Get commits to tests path in last 90 days
            since_date = (datetime.now() - timedelta(days=90)).isoformat()
            
            # Try multiple common test directory patterns
            test_paths = ['tests', 'test', 'testing']
            
            for path in test_paths:
                url = f"https://api.github.com/repos/{repo_full_name}/commits"
                params = {
                    'path': path,
                    'since': since_date,
                    'per_page': 100
                }
                
                response = self.session.get(url, headers=self.headers, params=params, timeout=10)
                
                if self._rate_limit_wait(response):
                    response = self.session.get(url, headers=self.headers, params=params, timeout=10)
                
                if response.status_code == 200:
                    commits = response.json()
                    for commit in commits:
                        author = commit.get('author', {})
                        if author and author.get('login'):
                            committers[author['login']] += 1
                
                time.sleep(0.2)  # Small delay between requests
        
        except Exception as e:
            print(f"⚠️  Error extracting test committers for {repo_full_name}: {e}")
        
        return list(committers.items())
    
    def parse_codeowners_for_ci(self, repo_full_name: str) -> Dict[str, List[str]]:
        """Parse CODEOWNERS for .github/workflows and tests/** ownership"""
        ci_owners = defaultdict(list)
        
        try:
            # Try common CODEOWNERS file locations
            codeowners_paths = ['CODEOWNERS', '.github/CODEOWNERS', 'docs/CODEOWNERS']
            
            for path in codeowners_paths:
                url = f"https://api.github.com/repos/{repo_full_name}/contents/{path}"
                response = self.session.get(url, headers=self.headers, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    content = base64.b64decode(data['content']).decode('utf-8')
                    
                    # Parse CODEOWNERS for CI-related patterns
                    for line in content.split('\n'):
                        line = line.strip()
                        if line and not line.startswith('#'):
                            line = line.split('#')[0].strip()
                            if line:
                                parts = line.split()
                                if len(parts) >= 2:
                                    pattern = parts[0]
                                    owners = [o.lstrip('@') for o in parts[1:]]
                                    
                                    # Check if pattern matches CI/testing paths
                                    if any(ci_path in pattern for ci_path in ['.github/workflows', 'tests/', 'test/', '*.yml', '*.yaml']):
                                        for owner in owners:
                                            ci_owners[owner].append(pattern)
                    break  # Found CODEOWNERS file
        
        except Exception as e:
            print(f"⚠️  Error parsing CODEOWNERS for {repo_full_name}: {e}")
        
        return dict(ci_owners)
    
    def get_user_profile(self, username: str) -> Optional[Dict]:
        """Get detailed user profile information"""
        try:
            url = f"https://api.github.com/users/{username}"
            response = self.session.get(url, headers=self.headers, timeout=10)
            
            if self._rate_limit_wait(response):
                response = self.session.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
        
        except Exception as e:
            print(f"⚠️  Error getting profile for {username}: {e}")
        
        return None
    
    def check_org_membership(self, org: str, username: str) -> bool:
        """Check if user is a public member of organization"""
        try:
            url = f"https://api.github.com/orgs/{org}/members/{username}"
            response = self.session.get(url, headers=self.headers, timeout=10)
            
            if self._rate_limit_wait(response):
                response = self.session.get(url, headers=self.headers, timeout=10)
            
            return response.status_code == 204  # 204 = public member
        
        except Exception:
            return False
    
    def get_repo_permission(self, repo_full_name: str, username: str) -> Optional[str]:
        """Get user's permission level on repository"""
        try:
            url = f"https://api.github.com/repos/{repo_full_name}/collaborators/{username}/permission"
            response = self.session.get(url, headers=self.headers, timeout=10)
            
            if self._rate_limit_wait(response):
                response = self.session.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('permission', 'read')
        
        except Exception:
            pass
        
        return None
    
    def calculate_ci_expertise_score(self, lead: CILead) -> int:
        """Calculate CI expertise score (0-100)"""
        score = 0
        
        # Workflow authoring (40 points max)
        score += min(40, lead.workflow_commits_90d * 5)
        
        # Test contributions (30 points max)
        score += min(30, lead.test_commits_90d * 3)
        
        # CODEOWNERS responsibility (20 points max)
        if lead.codeowner_patterns:
            score += 20
        
        # Permission level (10 points max)
        if lead.permission_level in ['admin', 'maintain']:
            score += 10
        elif lead.permission_level == 'write':
            score += 5
        
        return min(100, score)
    
    def calculate_decision_maker_score(self, lead: CILead) -> int:
        """Calculate decision maker score (0-100)"""
        score = 0
        
        # Administrative permissions (40 points)
        if lead.permission_level == 'admin':
            score += 40
        elif lead.permission_level == 'maintain':
            score += 30
        
        # Organization membership (20 points)
        if lead.is_org_member:
            score += 20
        
        # Company in profile (15 points)
        if lead.company:
            score += 15
        
        # High follower count suggests influence (15 points)
        if lead.followers > 100:
            score += 15
        elif lead.followers > 50:
            score += 10
        elif lead.followers > 20:
            score += 5
        
        # Bio suggests seniority (10 points)
        if lead.bio and any(title in lead.bio.lower() for title in ['cto', 'director', 'lead', 'senior', 'principal', 'architect']):
            score += 10
        
        return min(100, score)
    
    def classify_role_type(self, lead: CILead) -> str:
        """Classify as director, maintainer, or contributor"""
        if lead.decision_maker_score >= 60:
            return "director"
        elif lead.ci_expertise_score >= 50:
            return "maintainer"
        else:
            return "contributor"
    
    def assign_tier(self, lead: CILead) -> str:
        """Assign A/B/C tier based on overall score"""
        if lead.overall_score >= 70:
            return "A"
        elif lead.overall_score >= 50:
            return "B"
        else:
            return "C"
    
    def create_ci_lead(self, username: str, repo: Dict, signal_data: Dict) -> Optional[CILead]:
        """Create a CILead object from collected data"""
        # Get user profile
        profile = self.get_user_profile(username)
        if not profile:
            return None
        
        # Create unique lead ID
        lead_id = hashlib.md5(f"{username}:{repo['full_name']}".encode()).hexdigest()
        
        # Skip if already processed
        if lead_id in self.leads:
            return None
        
        # Extract email from commits if available
        email = None
        # This would require additional API calls to get commit details
        
        # Get repository permission
        permission = self.get_repo_permission(repo['full_name'], username)
        
        # Check org membership
        org = repo['full_name'].split('/')[0]
        is_org_member = self.check_org_membership(org, username)
        
        # Create lead object
        lead = CILead(
            # Identity
            lead_id=lead_id,
            login=username,
            github_id=profile.get('id', 0),
            name=profile.get('name'),
            
            # Contact & Company
            email=email,
            company=profile.get('company'),
            location=profile.get('location'),
            bio=profile.get('bio'),
            
            # Repository Context
            repo_full_name=repo['full_name'],
            repo_description=repo.get('description'),
            repo_stars=repo.get('stargazers_count', 0),
            repo_language=repo.get('language'),
            repo_topics=','.join(repo.get('topics', [])),
            
            # CI/DevOps Signals
            signal_type=signal_data.get('signal_type', 'unknown'),
            workflow_commits_90d=signal_data.get('workflow_commits', 0),
            test_commits_90d=signal_data.get('test_commits', 0),
            codeowner_patterns=','.join(signal_data.get('codeowner_patterns', [])),
            
            # Role Classification
            is_org_member=is_org_member,
            permission_level=permission,
            
            # Activity Metrics
            followers=profile.get('followers', 0),
            public_repos=profile.get('public_repos', 0),
            account_created=profile.get('created_at'),
            last_activity=profile.get('updated_at'),
        )
        
        # Calculate scores
        lead.ci_expertise_score = self.calculate_ci_expertise_score(lead)
        lead.decision_maker_score = self.calculate_decision_maker_score(lead)
        lead.overall_score = int((lead.ci_expertise_score + lead.decision_maker_score) / 2)
        lead.role_type = self.classify_role_type(lead)
        lead.tier = self.assign_tier(lead)
        
        self.leads.add(lead_id)
        return lead
    
    def _init_csv_file(self):
        """Initialize CSV file for incremental writing"""
        if self.output_path and not self.csv_initialized:
            self.csv_file = open(self.output_path, 'w', newline='', encoding='utf-8')
            
            fieldnames = [
                'lead_id', 'login', 'github_id', 'name', 'email', 'company', 'location', 'bio',
                'repo_full_name', 'repo_description', 'repo_stars', 'repo_language', 'repo_topics',
                'signal_type', 'workflow_files_authored', 'test_commits_90d', 'workflow_commits_90d', 'codeowner_patterns',
                'role_type', 'is_org_member', 'permission_level',
                'followers', 'public_repos', 'contributions_last_year', 'account_created', 'last_activity',
                'ci_expertise_score', 'decision_maker_score', 'overall_score', 'tier'
            ]
            
            self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=fieldnames)
            self.csv_writer.writeheader()
            self.csv_file.flush()
            self.csv_initialized = True
    
    def _write_lead_to_csv(self, lead: CILead):
        """Write a single lead to CSV file immediately"""
        if self.csv_writer:
            self.csv_writer.writerow(lead.to_dict())
            self.csv_file.flush()
    
    def _close_csv_file(self):
        """Close CSV file"""
        if self.csv_file:
            self.csv_file.close()
            self.csv_file = None
            self.csv_writer = None
    
    def process_repository(self, repo: Dict) -> List[CILead]:
        """Process a single repository to extract CI leads"""
        repo_name = repo['full_name']
        leads = []
        
        print(f"🔧 Processing {repo_name}...")
        
        # 1. Extract workflow authors
        workflow_authors = self.extract_workflow_authors(repo_name)
        
        # 2. Extract test committers
        test_committers = self.extract_test_committers(repo_name)
        
        # 3. Parse CODEOWNERS for CI patterns
        ci_codeowners = self.parse_codeowners_for_ci(repo_name)
        
        # Combine all signals
        all_users = set()
        user_signals = defaultdict(dict)
        
        # Process workflow authors
        for username, commit_count in workflow_authors:
            all_users.add(username)
            user_signals[username]['signal_type'] = 'workflow_author'
            user_signals[username]['workflow_commits'] = commit_count
        
        # Process test committers
        for username, commit_count in test_committers:
            all_users.add(username)
            if username not in user_signals:
                user_signals[username]['signal_type'] = 'test_committer'
            user_signals[username]['test_commits'] = commit_count
        
        # Process CODEOWNERS
        for username, patterns in ci_codeowners.items():
            all_users.add(username)
            if username not in user_signals:
                user_signals[username]['signal_type'] = 'codeowner'
            user_signals[username]['codeowner_patterns'] = patterns
        
        # Create leads for each user
        for username in all_users:
            try:
                signal_data = user_signals.get(username, {})
                lead = self.create_ci_lead(username, repo, signal_data)
                
                if lead:
                    leads.append(lead)
                    self.all_leads.append(lead)
                    
                    if self.output_path:
                        self._write_lead_to_csv(lead)
                    
                    print(f"   ✅ Added {username} ({lead.role_type}, tier {lead.tier})")
                
                time.sleep(0.1)  # Small delay between user requests
                
            except Exception as e:
                print(f"   ❌ Error processing {username}: {e}")
        
        return leads
    
    def scrape(self):
        """Main scraping logic"""
        print("🚀 Starting CI/DevOps Lead Scraping...")
        
        # Initialize CSV
        if self.output_path:
            self._init_csv_file()
        
        # 1. Search for repositories with CI activity
        repos = self.search_ci_repositories()
        print(f"📊 Found {len(repos)} repositories with CI activity")
        
        # 2. Process each repository
        repo_pbar = tqdm(repos, desc="Processing repos", unit="repo")
        
        for repo in repo_pbar:
            repo_pbar.set_description(f"Processing {repo['full_name']}")
            
            try:
                leads = self.process_repository(repo)
                repo_pbar.set_postfix(leads=len(self.all_leads))
                
            except Exception as e:
                print(f"❌ Error processing {repo['full_name']}: {e}")
            
            # Rate limiting
            time.sleep(self.config.get('delay', 1.0))
        
        repo_pbar.close()
        
        # 3. Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print comprehensive summary of results"""
        if not self.all_leads:
            print("\n📭 No leads found")
            return
        
        print(f"\n📊 CI/DEVOPS LEAD SUMMARY ({len(self.all_leads)} total)")
        print("=" * 80)
        
        # Role distribution
        role_counts = Counter(lead.role_type for lead in self.all_leads)
        print(f"\n👥 ROLE DISTRIBUTION:")
        for role, count in role_counts.most_common():
            print(f"   • {role.title()}: {count} ({count/len(self.all_leads)*100:.1f}%)")
        
        # Tier distribution
        tier_counts = Counter(lead.tier for lead in self.all_leads)
        print(f"\n🎯 TIER DISTRIBUTION:")
        for tier in ['A', 'B', 'C']:
            count = tier_counts.get(tier, 0)
            print(f"   • Tier {tier}: {count} ({count/len(self.all_leads)*100:.1f}%)")
        
        # Signal type distribution
        signal_counts = Counter(lead.signal_type for lead in self.all_leads)
        print(f"\n🔍 SIGNAL DISTRIBUTION:")
        for signal, count in signal_counts.most_common():
            print(f"   • {signal.replace('_', ' ').title()}: {count}")
        
        # Top companies
        companies = [lead.company for lead in self.all_leads if lead.company]
        if companies:
            company_counts = Counter(companies)
            print(f"\n🏢 TOP COMPANIES:")
            for company, count in company_counts.most_common(10):
                print(f"   • {company}: {count}")
        
        # Directors vs Maintainers
        directors = [lead for lead in self.all_leads if lead.role_type == 'director']
        maintainers = [lead for lead in self.all_leads if lead.role_type == 'maintainer']
        
        print(f"\n🎯 KEY TARGETS:")
        print(f"   • Directors (decision makers): {len(directors)}")
        print(f"   • Maintainers (practitioners): {len(maintainers)}")
        
        # Average scores
        avg_ci_score = sum(lead.ci_expertise_score for lead in self.all_leads) / len(self.all_leads)
        avg_dm_score = sum(lead.decision_maker_score for lead in self.all_leads) / len(self.all_leads)
        
        print(f"\n📈 AVERAGE SCORES:")
        print(f"   • CI Expertise: {avg_ci_score:.1f}/100")
        print(f"   • Decision Maker: {avg_dm_score:.1f}/100")
        
        if self.output_path:
            print(f"\n💾 Results saved to: {self.output_path}")
        
        print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description='GitHub CI/DevOps Lead Scraper')
    parser.add_argument('--config', default='config.yaml', help='Config file path')
    parser.add_argument('--out', default='data/ci_leads.csv', help='Output CSV path')
    parser.add_argument('--max-repos', type=int, default=100, help='Maximum repositories to process')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between requests (seconds)')
    parser.add_argument('--print-only', action='store_true', help='Only print results, do not save')
    args = parser.parse_args()
    
    # Get GitHub token
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if not token:
        print("❌ Error: GITHUB_TOKEN environment variable required")
        print("   Get a token at: https://github.com/settings/tokens")
        sys.exit(1)
    
    # Create config
    config = {
        'limits': {'max_repos': args.max_repos},
        'delay': args.delay
    }
    
    # Create output directory
    output_path = None if args.print_only else args.out
    if output_path:
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
    
    # Run scraper
    scraper = GitHubCIScraper(token, config, output_path)
    scraper.scrape()
    
    # Close CSV
    if output_path:
        scraper._close_csv_file()


if __name__ == '__main__':
    main()
