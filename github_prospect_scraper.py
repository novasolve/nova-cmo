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
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import yaml
import argparse
from dataclasses import dataclass, asdict


@dataclass
class Prospect:
    """Represents a GitHub prospect/contributor"""
    lead_id: str
    login: str
    name: Optional[str]
    company: Optional[str]
    email_public_commit: Optional[str]
    repo_full_name: str
    signal: str
    signal_type: str  # 'pr' or 'commit'
    signal_at: str
    topics: str
    language: str
    stars: int
    
    def to_dict(self):
        return asdict(self)


class GitHubScraper:
    """Scrapes GitHub for prospect data"""
    
    def __init__(self, token: str, config: dict):
        self.token = token
        self.config = config
        self.session = self._create_session()
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.prospects: Set[str] = set()  # Track unique lead_ids
        self.all_prospects: List[Prospect] = []
        
    def _create_session(self):
        """Create session with retry logic"""
        session = requests.Session()
        retry = Retry(
            total=5,
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
            
            response = self.session.get(url, headers=self.headers, params=params)
            
            if self._rate_limit_wait(response):
                continue
                
            if response.status_code != 200:
                print(f"Error searching repos: {response.status_code}")
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
        
        response = self.session.get(url, headers=self.headers, params=params)
        
        if self._rate_limit_wait(response):
            response = self.session.get(url, headers=self.headers, params=params)
            
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
                            'signal_at': pr['updated_at']
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
        
        response = self.session.get(url, headers=self.headers, params=params)
        
        if self._rate_limit_wait(response):
            response = self.session.get(url, headers=self.headers, params=params)
            
        if response.status_code == 200:
            commits = response.json()
            for commit in commits:
                if commit.get('author') and commit['author']['type'] == 'User':
                    author_data = {
                        'user': commit['author'],
                        'signal': f"committed: {commit['commit']['message'][:50]}",
                        'signal_type': 'commit',
                        'signal_at': commit['commit']['author']['date']
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
        response = self.session.get(url, headers=self.headers)
        
        if self._rate_limit_wait(response):
            response = self.session.get(url, headers=self.headers)
            
        if response.status_code == 200:
            return response.json()
        return {}
        
    def create_prospect(self, author_data: Dict, repo: Dict) -> Optional[Prospect]:
        """Create a Prospect object from author and repo data"""
        user = author_data['user']
        
        # Generate stable lead_id
        lead_id = hashlib.md5(f"{user['login']}_{repo['full_name']}".encode()).hexdigest()[:12]
        
        # Skip if we've already seen this lead
        if lead_id in self.prospects:
            return None
            
        # Get user details for name/company
        user_details = self.get_user_details(user['login'])
        
        prospect = Prospect(
            lead_id=lead_id,
            login=user['login'],
            name=user_details.get('name'),
            company=user_details.get('company'),
            email_public_commit=author_data.get('email'),
            repo_full_name=repo['full_name'],
            signal=author_data['signal'],
            signal_type=author_data['signal_type'],
            signal_at=author_data['signal_at'],
            topics=','.join(repo.get('topics', [])),
            language=repo.get('language', ''),
            stars=repo.get('stargazers_count', 0)
        )
        
        self.prospects.add(lead_id)
        return prospect
        
    def scrape(self):
        """Main scraping logic"""
        print(f"🔍 Searching for repos matching: {self.config['search']['query']}")
        repos = self.search_repos()
        print(f"📦 Found {len(repos)} repos to analyze")
        
        for i, repo in enumerate(repos):
            print(f"\n🏭 Processing {i+1}/{len(repos)}: {repo['full_name']}")
            
            # Get PR authors
            if self.config['limits']['per_repo_prs'] > 0:
                pr_authors = self.get_pr_authors(repo)
                print(f"  → Found {len(pr_authors)} PR authors")
                
                for author_data in pr_authors:
                    prospect = self.create_prospect(author_data, repo)
                    if prospect:
                        self.all_prospects.append(prospect)
                        
            # Get commit authors
            if self.config['limits']['per_repo_commits'] > 0:
                commit_authors = self.get_commit_authors(repo)
                print(f"  → Found {len(commit_authors)} commit authors")
                
                for author_data in commit_authors:
                    prospect = self.create_prospect(author_data, repo)
                    if prospect:
                        self.all_prospects.append(prospect)
                        
            # Check if we've hit our people limit
            if len(self.all_prospects) >= self.config['limits']['max_people']:
                print(f"\n✅ Reached max people limit ({self.config['limits']['max_people']})")
                break
                
            # Be nice to GitHub
            time.sleep(self.config.get('delay', 1))
            
        print(f"\n📊 Total unique prospects found: {len(self.all_prospects)}")
        
    def export_csv(self, output_path: str):
        """Export prospects to CSV"""
        if not self.all_prospects:
            print("No prospects to export")
            return
            
        fieldnames = list(self.all_prospects[0].to_dict().keys())
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for prospect in self.all_prospects:
                writer.writerow(prospect.to_dict())
                
        print(f"✅ Exported {len(self.all_prospects)} prospects to {output_path}")


def main():
    parser = argparse.ArgumentParser(description='GitHub Prospect Scraper')
    parser.add_argument('--config', default='config.yaml', help='Config file path')
    parser.add_argument('--out', default='data/prospects.csv', help='Output CSV path')
    args = parser.parse_args()
    
    # Check for GitHub token
    token = os.environ.get('GITHUB_TOKEN')
    if not token:
        print("❌ Error: GITHUB_TOKEN environment variable not set")
        print("Get a token at: https://github.com/settings/tokens")
        sys.exit(1)
        
    # Load config
    try:
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
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
        
    # Create output directory
    os.makedirs(os.path.dirname(args.out) or '.', exist_ok=True)
    
    # Run scraper
    scraper = GitHubScraper(token, config)
    scraper.scrape()
    scraper.export_csv(args.out)


if __name__ == '__main__':
    main()
