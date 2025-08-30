#!/usr/bin/env python3
"""
Repository Enrichment System
Fetches detailed repo metadata, CI health, activity patterns, and technical signals
"""

import os
import json
import time
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class RepoEnricher:
    """Enriches repository data with comprehensive technical and activity signals"""

    def __init__(self, github_token: str, cache_dir: str = "lead_intelligence/data/cache"):
        self.github_token = github_token
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': self._get_auth_header(github_token),
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'leads-intelligence/1.0'
        })

        self.rate_limiter = {'last_request': 0, 'min_delay': 1.0}

    def _get_auth_header(self, token: str) -> str:
        """Get the appropriate authorization header based on token format"""
        token = token.strip()

        # Detect token type and use appropriate authorization method
        if token.startswith('ghp_'):
            # Classic personal access token - use token auth
            return f'token {token}'
        elif token.startswith('github_token_'):
            # Fine-grained personal access token - use Bearer auth
            return f'Bearer {token}'
        else:
            # Unknown format - try Bearer first (GitHub supports both for most tokens)
            return f'Bearer {token}'

    def _rate_limit_wait(self):
        """Implement rate limiting"""
        now = time.time()
        time_since_last = now - self.rate_limiter['last_request']
        if time_since_last < self.rate_limiter['min_delay']:
            time.sleep(self.rate_limiter['min_delay'] - time_since_last)
        self.rate_limiter['last_request'] = time.time()

    def _make_request(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make rate-limited GitHub API request"""
        self._rate_limit_wait()

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request failed for {url}: {e}")
            return None

    def enrich_repo(self, repo_full_name: str) -> Dict[str, Any]:
        """
        Create comprehensive repo snapshot following the enrichment schema
        """
        cache_key = f"repo_{repo_full_name.replace('/', '_')}.json"
        cache_path = self.cache_dir / cache_key

        # Check cache first (24h TTL)
        if cache_path.exists():
            cache_age = time.time() - cache_path.stat().st_mtime
            if cache_age < 86400:  # 24 hours
                with open(cache_path, 'r') as f:
                    return json.load(f)

        logger.info(f"Enriching repository: {repo_full_name}")

        # Basic repo data
        repo_data = self._get_repo_basic_data(repo_full_name)
        if not repo_data:
            return self._empty_enrichment(repo_full_name)

        # Enhanced metadata
        enriched = {
            'repo': repo_full_name,
            'default_branch': repo_data.get('default_branch', 'main'),
            'stars': repo_data.get('stargazers_count', 0),
            'forks': repo_data.get('forks_count', 0),
            'watchers': repo_data.get('watchers_count', 0),
            'license': (repo_data.get('license') or {}).get('name'),
            'languages': self._get_repo_languages(repo_full_name),
            'activity': self._get_activity_metrics(repo_full_name),
            'ci': self._get_ci_signals(repo_full_name, repo_data),
            'tests': self._get_test_signals(repo_full_name),
            'prs': self._get_pr_signals(repo_full_name),
            'issues': self._get_issue_signals(repo_full_name),
            'enrichment_timestamp': datetime.now().isoformat(),
            'cache_used': False
        }

        # Cache the result
        with open(cache_path, 'w') as f:
            json.dump(enriched, f, indent=2, default=str)

        return enriched

    def _get_repo_basic_data(self, repo_full_name: str) -> Optional[Dict]:
        """Get basic repository information"""
        url = f"https://api.github.com/repos/{repo_full_name}"
        return self._make_request(url)

    def _get_repo_languages(self, repo_full_name: str) -> List[str]:
        """Get repository languages"""
        url = f"https://api.github.com/repos/{repo_full_name}/languages"
        data = self._make_request(url)
        if data:
            # Return top 3 languages by bytes
            sorted_langs = sorted(data.items(), key=lambda x: x[1], reverse=True)
            return [lang for lang, _ in sorted_langs[:3]]
        return []

    def _get_activity_metrics(self, repo_full_name: str) -> Dict[str, Any]:
        """Get repository activity metrics"""
        # Get commits in last 30 days
        since = (datetime.now() - timedelta(days=30)).isoformat()
        url = f"https://api.github.com/repos/{repo_full_name}/commits"
        params = {'since': since, 'per_page': 100}

        commits_data = self._make_request(url, params)
        commits_30d = len(commits_data) if commits_data else 0

        # Get latest commit for age calculation
        latest_commit = None
        if commits_data:
            latest_commit = commits_data[0]

        last_commit_age_days = None
        if latest_commit and latest_commit.get('commit', {}).get('author', {}).get('date'):
            commit_date = datetime.fromisoformat(
                latest_commit['commit']['author']['date'].replace('Z', '+00:00')
            )
            # Make current datetime timezone-aware to match commit_date
            now = datetime.now(timezone.utc)
            last_commit_age_days = (now - commit_date).days

        return {
            'commits_30d': commits_30d,
            'last_commit_age_days': last_commit_age_days
        }

    def _get_ci_signals(self, repo_full_name: str, repo_data: Dict) -> Dict[str, Any]:
        """Extract CI and workflow signals"""
        ci_signals = {
            'provider': None,
            'workflows': [],
            'fail_rate_30d': 0.0,
            'flake_hints': []
        }

        # Check for GitHub Actions workflows
        workflows_url = f"https://api.github.com/repos/{repo_full_name}/actions/workflows"
        workflows_data = self._make_request(workflows_url)

        if workflows_data and workflows_data.get('workflows'):
            ci_signals['provider'] = 'github_actions'
            ci_signals['workflows'] = [
                w['name'] for w in workflows_data['workflows'][:5]  # Top 5 workflows
            ]

            # Get recent workflow runs to analyze failure patterns
            runs_url = f"https://api.github.com/repos/{repo_full_name}/actions/runs"
            runs_params = {'per_page': 50}
            runs_data = self._make_request(runs_url, runs_params)

            if runs_data and runs_data.get('workflow_runs'):
                runs = runs_data['workflow_runs']
                total_runs = len(runs)
                failed_runs = sum(1 for r in runs if r['conclusion'] == 'failure')

                if total_runs > 0:
                    ci_signals['fail_rate_30d'] = failed_runs / total_runs

                # Look for flake indicators
                flake_keywords = ['flaky', 'flak', 'timeout', 'race', 'rerun', 'unstable']
                for run in runs[:20]:  # Check recent runs
                    if run.get('name'):
                        name_lower = run['name'].lower()
                        for keyword in flake_keywords:
                            if keyword in name_lower:
                                ci_signals['flake_hints'].append(f"{run['name']}: {keyword}")
                                break

        return ci_signals

    def _get_test_signals(self, repo_full_name: str) -> Dict[str, Any]:
        """Extract test framework and testing signals"""
        test_signals = {
            'framework': None,
            'has_tests': False,
            'failure_keywords_90d': [],
            'coverage_badge': False
        }

        # Check for test files and frameworks
        contents_url = f"https://api.github.com/repos/{repo_full_name}/contents"
        contents_data = self._make_request(contents_url)

        if contents_data:
            file_names = [item['name'].lower() for item in contents_data if item['type'] == 'file']

            # Check for test directories and files
            has_test_files = any('test' in name or 'spec' in name for name in file_names)
            has_test_dir = any(item['name'] == 'tests' for item in contents_data
                             if item['type'] == 'dir')

            test_signals['has_tests'] = has_test_files or has_test_dir

            # Detect test frameworks
            if any('pytest' in name or 'tox.ini' in name for name in file_names):
                test_signals['framework'] = 'pytest'
            elif any('jest' in name or 'mocha' in name for name in file_names):
                test_signals['framework'] = 'jest'
            elif any('junit' in name for name in file_names):
                test_signals['framework'] = 'junit'
            elif any('go.mod' in name for name in file_names):
                test_signals['framework'] = 'go_test'

            # Check for coverage badges (common in README)
            if any('coverage' in name.lower() for name in file_names):
                test_signals['coverage_badge'] = True

        # Get recent issues/PRs with test-related keywords
        failure_keywords = ['flaky', 'flak', 'timeout', 'test failure', 'ci failure']
        # This would require additional API calls to search issues/PRs
        # For now, we'll leave this as an empty list
        test_signals['failure_keywords_90d'] = []

        return test_signals

    def _get_pr_signals(self, repo_full_name: str) -> Dict[str, Any]:
        """Extract PR-related signals"""
        pr_signals = {
            'open': 0,
            'with_failing_checks': 0,
            'median_time_to_green_hours': None
        }

        # Get open PRs
        prs_url = f"https://api.github.com/repos/{repo_full_name}/pulls"
        prs_params = {'state': 'open', 'per_page': 50}
        prs_data = self._make_request(prs_url, prs_params)

        if prs_data:
            pr_signals['open'] = len(prs_data)

            # Check for failing checks (simplified)
            failing_count = 0
            for pr in prs_data[:10]:  # Check first 10 PRs
                # This would require additional API calls to get check runs
                # For now, we'll use a simple heuristic
                if pr.get('title', '').lower().find('fix') != -1:
                    failing_count += 1

            pr_signals['with_failing_checks'] = failing_count

        return pr_signals

    def _get_issue_signals(self, repo_full_name: str) -> Dict[str, Any]:
        """Extract issue-related signals"""
        issue_signals = {
            'open': 0,
            'labels_present': []
        }

        # Get repository data for open issues count
        repo_data = self._get_repo_basic_data(repo_full_name)
        if repo_data:
            issue_signals['open'] = repo_data.get('open_issues_count', 0)

        # Get recent issues to check for labels
        issues_url = f"https://api.github.com/repos/{repo_full_name}/issues"
        issues_params = {'state': 'open', 'per_page': 20}
        issues_data = self._make_request(issues_url, issues_params)

        if issues_data:
            all_labels = []
            for issue in issues_data:
                if issue.get('labels'):
                    all_labels.extend([label['name'] for label in issue['labels']])

            # Get unique labels and filter for relevant ones
            unique_labels = list(set(all_labels))
            relevant_labels = [label for label in unique_labels
                             if any(keyword in label.lower()
                                   for keyword in ['ci', 'test', 'good first issue', 'bug'])]

            issue_signals['labels_present'] = relevant_labels[:5]  # Top 5 relevant labels

        return issue_signals

    def _empty_enrichment(self, repo_full_name: str) -> Dict[str, Any]:
        """Return empty enrichment structure for failed requests"""
        return {
            'repo': repo_full_name,
            'default_branch': None,
            'stars': 0,
            'forks': 0,
            'watchers': 0,
            'license': None,
            'languages': [],
            'activity': {'commits_30d': 0, 'last_commit_age_days': None},
            'ci': {'provider': None, 'workflows': [], 'fail_rate_30d': 0.0, 'flake_hints': []},
            'tests': {'framework': None, 'has_tests': False, 'failure_keywords_90d': [], 'coverage_badge': False},
            'prs': {'open': 0, 'with_failing_checks': 0, 'median_time_to_green_hours': None},
            'issues': {'open': 0, 'labels_present': []},
            'enrichment_timestamp': datetime.now().isoformat(),
            'cache_used': False,
            'error': 'Failed to fetch repo data'
        }
