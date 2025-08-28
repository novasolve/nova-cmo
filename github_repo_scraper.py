#!/usr/bin/env python3
"""
GitHub Repository Scraper for Attio
Collects repository data from GitHub based on search criteria
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
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import yaml
import argparse
from dataclasses import dataclass, asdict
from urllib.parse import urlparse
from tqdm import tqdm


@dataclass
class Repo:
    """Represents a GitHub repository with Attio schema"""
    # Identity
    repo_full_name: str  # Required, Unique - e.g., scikit-hep/awkward
    repo_name: str  # slug only, e.g., awkward
    owner_login: str  # org/user that owns the repo
    host: str = "GitHub"  # Select: GitHub, GitLab, Bitbucket
    
    # Metadata
    description: Optional[str] = None  # Long text
    topics: str = ""  # Multi-select (tags) - comma-separated list
    primary_language: Optional[str] = None  # main language of repo
    license: Optional[str] = None
    
    # Popularity/Metrics
    stars: int = 0  # Number
    forks: int = 0  # Number
    watchers: int = 0  # Number
    open_issues: int = 0  # Number
    is_fork: bool = False  # Checkbox
    is_archived: bool = False  # Checkbox
    
    # Timestamps
    created_at: Optional[str] = None  # Timestamp
    updated_at: Optional[str] = None  # Timestamp
    pushed_at: Optional[str] = None  # Timestamp
    
    # URLs
    html_url: Optional[str] = None  # URL - public repo link
    api_url: Optional[str] = None  # URL - GitHub API link for this repo
    
    # Convenience
    recent_push_30d: bool = False  # Computed during import
    
    def to_dict(self):
        return asdict(self)


class GitHubRepoScraper:
    """Scrapes GitHub repositories based on search criteria"""
    
    def __init__(self, token: str, config: dict, output_path: str = None):
        self.token = token
        self.config = config
        self.output_path = output_path
        self.session = self._create_session()
        self.headers = {
            'Accept': 'application/vnd.github.v3+json'
        }
        # Only add auth header if token is provided and valid
        if token and token.strip():
            self.headers['Authorization'] = f'token {token}'
        self.repos: Set[str] = set()  # Track unique repo full names
        self.all_repos: List[Repo] = []
        self.csv_file = None
        self.csv_writer = None
        self.csv_initialized = False
        
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
    
    def _init_csv_file(self):
        """Initialize CSV file for incremental writing"""
        if self.output_path and not self.csv_initialized:
            self.csv_file = open(self.output_path, 'w', newline='', encoding='utf-8')
            # Define all fieldnames from Repo dataclass matching Attio schema
            fieldnames = [
                # Identity
                'repo_full_name', 'repo_name', 'owner_login', 'host',
                # Metadata
                'description', 'topics', 'primary_language', 'license',
                # Popularity/Metrics
                'stars', 'forks', 'watchers', 'open_issues', 'is_fork', 'is_archived',
                # Timestamps
                'created_at', 'updated_at', 'pushed_at',
                # URLs
                'html_url', 'api_url',
                # Convenience
                'recent_push_30d'
            ]
            self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=fieldnames)
            self.csv_writer.writeheader()
            self.csv_file.flush()
            self.csv_initialized = True
    
    def _write_repo_to_csv(self, repo: Repo):
        """Write a single repo to CSV file immediately"""
        if self.csv_writer:
            self.csv_writer.writerow(repo.to_dict())
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
                print(f"Error searching repos: {response.status_code}")
                break
                
            data = response.json()
            repos.extend(data.get('items', []))
            
            if len(data.get('items', [])) < per_page:
                break
                
            page += 1
            time.sleep(self.config.get('delay', 1))  # Be nice to GitHub
            
        return repos[:max_repos]
    
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
    
    def get_repo_details(self, owner: str, repo_name: str) -> Optional[Dict]:
        """Get detailed repository information"""
        url = f"https://api.github.com/repos/{owner}/{repo_name}"
        response = self.session.get(url, headers=self.headers, timeout=10)
        
        if self._rate_limit_wait(response):
            response = self.session.get(url, headers=self.headers, timeout=10)
            
        if response.status_code == 200:
            return response.json()
        return None
    
    def get_user_repos(self, username: str, limit: int = 100) -> List[Dict]:
        """Get user's repositories"""
        all_repos = []
        page = 1
        
        while len(all_repos) < limit:
            url = f"https://api.github.com/users/{username}/repos"
            params = {
                'sort': 'updated',
                'direction': 'desc',
                'per_page': min(100, limit - len(all_repos)),
                'page': page
            }
            
            response = self.session.get(url, headers=self.headers, params=params, timeout=10)
            
            if self._rate_limit_wait(response):
                response = self.session.get(url, headers=self.headers, params=params, timeout=10)
                
            if response.status_code == 200:
                repos = response.json()
                if not repos:
                    break
                all_repos.extend(repos)
                page += 1
            else:
                print(f"Error fetching user repos: {response.status_code}")
                break
                
        return all_repos[:limit]
    
    def create_repo_object(self, repo_data: Dict) -> Optional[Repo]:
        """Create a Repo object from GitHub API data"""
        full_name = repo_data.get('full_name')
        
        # Skip if we've already seen this repo
        if full_name in self.repos:
            return None
        
        # Extract license name
        license_name = None
        if repo_data.get('license'):
            license_name = repo_data['license'].get('name') or repo_data['license'].get('spdx_id')
        
        # Compute recent push flag (30 days)
        pushed_at = repo_data.get('pushed_at')
        recent_push_30d = False
        if pushed_at:
            try:
                pushed_dt = datetime.fromisoformat(pushed_at.replace('Z', '+00:00'))
                recent_push_30d = (datetime.now(pushed_dt.tzinfo) - pushed_dt).days <= 30
            except Exception:
                recent_push_30d = False

        repo = Repo(
            # Identity
            repo_full_name=full_name,
            repo_name=repo_data.get('name'),
            owner_login=repo_data.get('owner', {}).get('login'),
            host="GitHub",
            
            # Metadata
            description=repo_data.get('description'),
            topics=','.join(repo_data.get('topics', [])),
            primary_language=repo_data.get('language'),
            license=license_name,
            
            # Popularity/Metrics
            stars=repo_data.get('stargazers_count', 0),
            forks=repo_data.get('forks_count', 0),
            watchers=repo_data.get('watchers_count', 0),
            open_issues=repo_data.get('open_issues_count', 0),
            is_fork=repo_data.get('fork', False),
            is_archived=repo_data.get('archived', False),
            
            # Timestamps
            created_at=repo_data.get('created_at'),
            updated_at=repo_data.get('updated_at'),
            pushed_at=pushed_at,
            
            # URLs
            html_url=repo_data.get('html_url'),
            api_url=repo_data.get('url'),
            
            # Convenience
            recent_push_30d=recent_push_30d
        )
        
        self.repos.add(full_name)
        
        # Write to CSV immediately if incremental writing is enabled
        if self.output_path:
            self._write_repo_to_csv(repo)
            
        return repo
    
    def scrape_from_url(self, github_url: str):
        """Scrape repositories from a GitHub URL (user profile or repository)"""
        try:
            parsed = self.parse_github_url(github_url)
            
            if parsed['type'] == 'user':
                username = parsed['username']
                
                # Get user's repositories
                repos = self.get_user_repos(username, limit=self.config['limits']['max_repos'])
                
                if repos:
                    pbar = tqdm(repos, desc=f"Processing {username}'s repos", unit="repo")
                    for repo_data in pbar:
                        repo = self.create_repo_object(repo_data)
                        if repo:
                            self.all_repos.append(repo)
                            pbar.set_description(f"Added {repo.repo_full_name}")
                else:
                    tqdm.write(f"❌ No repositories found for user {username}")
                    
            elif parsed['type'] == 'repo':
                owner = parsed['owner']
                repo_name = parsed['repo']
                
                # Get repository details
                repo_data = self.get_repo_details(owner, repo_name)
                
                if repo_data:
                    repo = self.create_repo_object(repo_data)
                    if repo:
                        self.all_repos.append(repo)
                        tqdm.write(f"✅ Added repository: {repo.repo_full_name}")
                else:
                    tqdm.write(f"❌ Repository {owner}/{repo_name} not found")
                    
        except Exception as e:
            tqdm.write(f"❌ Error processing URL {github_url}: {e}")
    
    def print_repos_summary(self):
        """Print a summary of all found repositories"""
        if not self.all_repos:
            print("\n📭 No repositories found")
            return
            
        print(f"\n📊 REPOSITORY SUMMARY ({len(self.all_repos)} total)")
        print("=" * 80)
        
        for i, repo in enumerate(self.all_repos, 1):
            print(f"\n{i:2d}. {repo.repo_full_name}")
            print(f"    🏢 Owner: {repo.owner_login}")
            print(f"    📝 Description: {repo.description or 'No description'}")
            print(f"    🏷️  Topics: {repo.topics or 'No topics'}")
            print(f"    💻 Language: {repo.primary_language or 'Not specified'}")
            print(f"    📜 License: {repo.license or 'No license'}")
            print(f"    ⭐ Stars: {repo.stars:,}")
            print(f"    🍴 Forks: {repo.forks:,}")
            print(f"    👁️  Watchers: {repo.watchers:,}")
            print(f"    🐛 Open Issues: {repo.open_issues:,}")
            print(f"    📅 Created: {repo.created_at}")
            print(f"    📅 Updated: {repo.updated_at}")
            print(f"    📅 Last Push: {repo.pushed_at}")
            print(f"    🔗 URL: {repo.html_url}")
            
            if repo.is_fork:
                print(f"    🍴 This is a fork")
            if repo.is_archived:
                print(f"    📦 This repository is archived")
        
        print("\n" + "=" * 80)
        
        # Summary stats
        with_description = sum(1 for r in self.all_repos if r.description)
        with_topics = sum(1 for r in self.all_repos if r.topics)
        with_license = sum(1 for r in self.all_repos if r.license)
        forked = sum(1 for r in self.all_repos if r.is_fork)
        archived = sum(1 for r in self.all_repos if r.is_archived)
        
        print(f"📈 STATS:")
        print(f"   • {with_description}/{len(self.all_repos)} have descriptions ({with_description/len(self.all_repos)*100:.1f}%)")
        print(f"   • {with_topics}/{len(self.all_repos)} have topics ({with_topics/len(self.all_repos)*100:.1f}%)")
        print(f"   • {with_license}/{len(self.all_repos)} have licenses ({with_license/len(self.all_repos)*100:.1f}%)")
        print(f"   • {forked} are forks ({forked/len(self.all_repos)*100:.1f}%)")
        print(f"   • {archived} are archived ({archived/len(self.all_repos)*100:.1f}%)")
        
        # Top languages
        languages = [r.primary_language for r in self.all_repos if r.primary_language]
        if languages:
            from collections import Counter
            top_languages = Counter(languages).most_common(5)
            print(f"\n💻 TOP LANGUAGES:")
            for language, count in top_languages:
                print(f"   • {language}: {count} repos")
        
        # Total stars
        total_stars = sum(r.stars for r in self.all_repos)
        avg_stars = total_stars / len(self.all_repos) if self.all_repos else 0
        print(f"\n⭐ TOTAL STARS: {total_stars:,} (avg: {avg_stars:.1f} per repo)")
        
        print(f"\n💾 Data saved to: {self.output_path or 'No output file specified'}")
        print("=" * 80)
    
    def scrape(self):
        """Main scraping logic"""
        # Initialize CSV file for incremental writing
        if self.output_path:
            self._init_csv_file()
            
        repos = self.search_repos()
        
        # Use tqdm for progress tracking
        repo_pbar = tqdm(repos, desc="Processing repos", unit="repo")
        
        for repo_data in repo_pbar:
            repo_pbar.set_description(f"Processing {repo_data['full_name']}")
            
            # Create repo object from search result
            repo = self.create_repo_object(repo_data)
            if repo:
                self.all_repos.append(repo)
                repo_pbar.set_postfix(total=len(self.all_repos))
            
            # Be nice to GitHub
            time.sleep(self.config.get('delay', 0.5))
        
        repo_pbar.close()
        
        # Print repos summary at the end
        self.print_repos_summary()
    
    def export_csv(self, output_path: str):
        """Export repositories to CSV"""
        if not self.all_repos:
            return
            
        # Use same fieldnames as init_csv_file
        fieldnames = [
            # Identity
            'repo_full_name', 'repo_name', 'owner_login', 'host',
            # Metadata
            'description', 'topics', 'primary_language', 'license',
            # Popularity/Metrics
            'stars', 'forks', 'watchers', 'open_issues', 'is_fork', 'is_archived',
            # Timestamps
            'created_at', 'updated_at', 'pushed_at',
            # URLs
            'html_url', 'api_url',
            # Convenience
            'recent_push_30d'
        ]
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for repo in self.all_repos:
                writer.writerow(repo.to_dict())


def main():
    parser = argparse.ArgumentParser(description='GitHub Repository Scraper for Attio')
    parser.add_argument('--config', default='config.yaml', help='Config file path')
    parser.add_argument('--out', default='data/repos.csv', help='Output CSV path')
    parser.add_argument('-n', '--max-repos', type=int, help='Maximum number of repos to process (overrides config)')
    parser.add_argument('--url', help='GitHub URL to scrape (user profile or repository)')
    parser.add_argument('--print-only', action='store_true', help='Only print results, do not save to CSV')
    args = parser.parse_args()
    
    # Check for GitHub token
    token = os.environ.get('GITHUB_TOKEN')
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
            'limits': {'max_repos': 50},
            'delay': 0.5
        }
        
        # Don't save to CSV if print-only mode
        output_path = None if args.print_only else args.out
        if output_path:
            os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        
        scraper = GitHubRepoScraper(token, config, output_path)
        
        # Initialize CSV if needed
        if output_path:
            scraper._init_csv_file()
        
        # Scrape from URL
        scraper.scrape_from_url(args.url)
        
        # Always print results in URL mode
        scraper.print_repos_summary()
        
        # Close CSV file
        if output_path:
            scraper._close_csv_file()
        
        return
        
    # Regular config-based mode
    try:
        with open(args.config, 'r') as f:
            config = yaml.safe_load(f)
            
        # Override max_repos if -n argument is provided
        if args.max_repos:
            config['limits']['max_repos'] = args.max_repos
            print(f"🔧 Overriding max_repos to {args.max_repos}")
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
                'max_repos': 50
            },
            'delay': 0.5
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
    scraper = GitHubRepoScraper(token, config, args.out)
    scraper.scrape()
    
    # Close CSV file if it was opened for incremental writing
    scraper._close_csv_file()
    
    # Also export using the traditional method (in case incremental writing wasn't used)
    if not scraper.csv_initialized:
        scraper.export_csv(args.out)


if __name__ == '__main__':
    main()
