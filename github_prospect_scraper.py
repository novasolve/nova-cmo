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
    
    def __init__(self, token: str, config: dict, output_path: str = None):
        self.token = token
        self.config = config
        self.output_path = output_path
        self.session = self._create_session()
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.prospects: Set[str] = set()  # Track unique lead_ids
        self.all_prospects: List[Prospect] = []
        self.csv_file = None
        self.csv_writer = None
        self.csv_initialized = False
        
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
            print(f"📝 Initialized CSV file: {self.output_path}")
    
    def _write_prospect_to_csv(self, prospect: Prospect):
        """Write a single prospect to CSV file immediately"""
        if self.csv_writer:
            self.csv_writer.writerow(prospect.to_dict())
            self.csv_file.flush()  # Ensure data is written immediately
            print(f"    ✅ Wrote prospect #{len(self.all_prospects)}: {prospect.login} ({prospect.repo_full_name})")
    
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
    
    def get_user_contributions(self, username: str) -> Dict:
        """Get user contribution statistics using GraphQL API"""
        # This would require GraphQL API access
        # For now, return empty dict - can be implemented later
        # query = '''
        # query($username: String!) {
        #   user(login: $username) {
        #     contributionsCollection {
        #       contributionCalendar {
        #         totalContributions
        #       }
        #       contributionYears
        #       totalCommitContributions
        #       totalPullRequestContributions
        #       totalIssueContributions
        #     }
        #   }
        # }
        # '''
        return {}
        
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
        
        # IMPORTANT: Skip if no email is available
        if not email_commit and not email_profile:
            print(f"    ⚠️  Skipping {user['login']} - no email found")
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
        
        # Get contribution stats (would require additional API call to GraphQL)
        # For now, set to None - can be enhanced later
        contributions_last_year = None
        
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
            total_contributions=None,
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
            print(f"    ✅ Wrote prospect #{len(self.all_prospects)}: {prospect.login} ({prospect.get_best_email()})")
            
        return prospect
        
    def scrape(self):
        """Main scraping logic"""
        # Initialize CSV file for incremental writing
        if self.output_path:
            self._init_csv_file()
            
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
                
        print(f"✅ Exported {len(self.all_prospects)} prospects to {output_path}")


def main():
    parser = argparse.ArgumentParser(description='GitHub Prospect Scraper')
    parser.add_argument('--config', default='config.yaml', help='Config file path')
    parser.add_argument('--out', default='data/prospects.csv', help='Output CSV path')
    parser.add_argument('-n', '--max-repos', type=int, help='Maximum number of repos to process (overrides config)')
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
    scraper = GitHubScraper(token, config, args.out)
    scraper.scrape()
    
    # Close CSV file if it was opened for incremental writing
    scraper._close_csv_file()
    
    # Also export using the traditional method (in case incremental writing wasn't used)
    if not scraper.csv_initialized:
        scraper.export_csv(args.out)


if __name__ == '__main__':
    main()
