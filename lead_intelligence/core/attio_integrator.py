#!/usr/bin/env python3
"""
Attio Integration System
Automatic import of intelligence data into Attio CRM
"""

import os
import json
import csv
import requests
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from pathlib import Path
import time
from urllib.parse import urljoin


logger = logging.getLogger(__name__)


class AttioIntegrator:
    """Attio API integration for automatic data import"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.config["api_token"]}',
            'Content-Type': 'application/json'
        })
        self.logger = logger
        self.rate_limiter = self._setup_rate_limiter()

    def _default_config(self) -> Dict[str, Any]:
        """Default Attio integration configuration"""
        return {
            'api_token': os.environ.get('ATTIO_API_TOKEN', ''),
            'base_url': 'https://api.attio.com/v2/',
            'workspace_id': os.environ.get('ATTIO_WORKSPACE_ID', ''),
            'batch_size': 50,
            'rate_limit_delay': 1.0,
            'max_retries': 3,
            'timeout': 30,
            'auto_create_lists': True,
            'validate_before_import': True,
            'backup_before_import': True
        }

    def _setup_rate_limiter(self):
        """Setup rate limiting"""
        return {
            'last_request': 0,
            'min_delay': self.config['rate_limit_delay']
        }

    def _rate_limit_wait(self):
        """Implement rate limiting"""
        now = time.time()
        time_since_last = now - self.rate_limiter['last_request']
        if time_since_last < self.rate_limiter['min_delay']:
            time.sleep(self.rate_limiter['min_delay'] - time_since_last)
        self.rate_limiter['last_request'] = time.time()

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None,
                     params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make authenticated request to Attio API"""
        url = urljoin(self.config['base_url'], endpoint)

        for attempt in range(self.config['max_retries']):
            try:
                self._rate_limit_wait()

                response = self.session.request(
                    method=method,
                    url=url,
                    json=data,
                    params=params,
                    timeout=self.config['timeout']
                )

                if response.status_code == 429:  # Rate limited
                    retry_after = int(response.headers.get('Retry-After', 60))
                    self.logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()
                return response.json()

            except requests.exceptions.RequestException as e:
                if attempt == self.config['max_retries'] - 1:
                    raise e
                self.logger.warning(f"Request failed (attempt {attempt + 1}): {e}")
                time.sleep(2 ** attempt)  # Exponential backoff

        raise Exception(f"Failed to make request after {self.config['max_retries']} attempts")

    def validate_connection(self) -> bool:
        """Validate Attio API connection"""
        try:
            # Try to get workspace info
            response = self._make_request('GET', 'workspaces')
            self.logger.info("Attio API connection validated successfully")
            return True
        except Exception as e:
            self.logger.error(f"Attio API connection failed: {e}")
            return False

    def import_people(self, people_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Import people data into Attio"""
        self.logger.info(f"Importing {len(people_data)} people records")

        results = {
            'total': len(people_data),
            'successful': 0,
            'failed': 0,
            'errors': [],
            'created': 0,
            'updated': 0
        }

        for person in people_data:
            try:
                result = self._import_person(person)
                if result['success']:
                    results['successful'] += 1
                    if result['created']:
                        results['created'] += 1
                    else:
                        results['updated'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append({
                        'record': person.get('login', 'unknown'),
                        'error': result['error']
                    })
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'record': person.get('login', 'unknown'),
                    'error': str(e)
                })

        self.logger.info(f"People import complete: {results['successful']}/{results['total']} successful")
        return results

    def _import_person(self, person: Dict[str, Any]) -> Dict[str, Any]:
        """Import a single person record"""
        try:
            # Prepare data according to Attio schema
            attio_data = self._transform_person_for_attio(person)

            # Check if person already exists
            existing = self._find_existing_person(person['login'])

            if existing:
                # Update existing record
                record_id = existing['id']['value']
                response = self._make_request(
                    'PUT',
                    f'objects/people/records/{record_id}',
                    attio_data
                )
                return {'success': True, 'created': False, 'updated': True}
            else:
                # Create new record
                response = self._make_request(
                    'POST',
                    'objects/people/records',
                    attio_data
                )
                return {'success': True, 'created': True, 'updated': False}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _transform_person_for_attio(self, person: Dict[str, Any]) -> Dict[str, Any]:
        """Transform person data to Attio format"""
        # Map fields according to Attio People object schema
        attio_person = {
            "data": {
                "login": {"value": person.get("login")},
                "id": {"value": person.get("id")},
                "node_id": {"value": person.get("node_id")},
                "lead_id": {"value": person.get("lead_id")},
                "name": {"value": person.get("name")},
                "company": {"value": person.get("company")},
                "location": {"value": person.get("location")},
                "bio": {"value": person.get("bio")},
                "pronouns": {"value": person.get("pronouns")},
                "public_repos": {"value": person.get("public_repos")},
                "public_gists": {"value": person.get("public_gists")},
                "followers": {"value": person.get("followers")},
                "following": {"value": person.get("following")},
                "html_url": {"value": person.get("html_url")},
                "avatar_url": {"value": person.get("avatar_url")},
                "github_user_url": {"value": person.get("github_user_url")},
                "api_url": {"value": person.get("api_url")}
            }
        }

        # Add emails if available
        emails = []
        if person.get("email_profile"):
            emails.append({"value": person["email_profile"]})
        if person.get("email_public_commit"):
            emails.append({"value": person["email_public_commit"]})

        if emails:
            attio_person["data"]["email_addresses"] = emails

        # Add timestamps
        if person.get("created_at"):
            attio_person["data"]["created_at"] = {"value": person["created_at"]}
        if person.get("updated_at"):
            attio_person["data"]["updated_at"] = {"value": person["updated_at"]}

        return attio_person

    def _find_existing_person(self, login: str) -> Optional[Dict[str, Any]]:
        """Find existing person by login"""
        try:
            response = self._make_request(
                'GET',
                'objects/people/records',
                params={
                    'filter[login][eq]': login,
                    'limit': 1
                }
            )

            records = response.get('data', [])
            if records:
                return records[0]
            return None

        except Exception as e:
            self.logger.warning(f"Error finding existing person {login}: {e}")
            return None

    def import_repos(self, repos_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Import repository data into Attio"""
        self.logger.info(f"Importing {len(repos_data)} repository records")

        results = {
            'total': len(repos_data),
            'successful': 0,
            'failed': 0,
            'errors': [],
            'created': 0,
            'updated': 0
        }

        for repo in repos_data:
            try:
                result = self._import_repo(repo)
                if result['success']:
                    results['successful'] += 1
                    if result['created']:
                        results['created'] += 1
                    else:
                        results['updated'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append({
                        'record': repo.get('repo_full_name', 'unknown'),
                        'error': result['error']
                    })
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'record': repo.get('repo_full_name', 'unknown'),
                    'error': str(e)
                })

        self.logger.info(f"Repository import complete: {results['successful']}/{results['total']} successful")
        return results

    def _import_repo(self, repo: Dict[str, Any]) -> Dict[str, Any]:
        """Import a single repository record"""
        try:
            attio_data = self._transform_repo_for_attio(repo)

            # Check if repo already exists
            existing = self._find_existing_repo(repo['repo_full_name'])

            if existing:
                record_id = existing['id']['value']
                response = self._make_request(
                    'PUT',
                    f'objects/repos/records/{record_id}',
                    attio_data
                )
                return {'success': True, 'created': False, 'updated': True}
            else:
                response = self._make_request(
                    'POST',
                    'objects/repos/records',
                    attio_data
                )
                return {'success': True, 'created': True, 'updated': False}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _transform_repo_for_attio(self, repo: Dict[str, Any]) -> Dict[str, Any]:
        """Transform repository data to Attio format"""
        attio_repo = {
            "data": {
                "repo_full_name": {"value": repo.get("repo_full_name")},
                "repo_name": {"value": repo.get("repo_name")},
                "owner_login": {"value": repo.get("owner_login")},
                "host": {"value": "GitHub"},
                "description": {"value": repo.get("description")},
                "primary_language": {"value": repo.get("language")},
                "license": {"value": repo.get("license")},
                "stars": {"value": repo.get("stars")},
                "forks": {"value": repo.get("forks")},
                "watchers": {"value": repo.get("watchers")},
                "open_issues": {"value": repo.get("open_issues")},
                "is_fork": {"value": repo.get("fork", False)},
                "is_archived": {"value": repo.get("archived", False)},
                "html_url": {"value": repo.get("html_url")},
                "api_url": {"value": repo.get("url")}
            }
        }

        # Add timestamps
        if repo.get("created_at"):
            attio_repo["data"]["created_at"] = {"value": repo["created_at"]}
        if repo.get("updated_at"):
            attio_repo["data"]["updated_at"] = {"value": repo["updated_at"]}
        if repo.get("pushed_at"):
            attio_repo["data"]["pushed_at"] = {"value": repo["pushed_at"]}

        # Add topics as multi-select
        if repo.get("topics"):
            attio_repo["data"]["topics"] = [{"value": topic} for topic in repo["topics"]]

        return attio_repo

    def _find_existing_repo(self, repo_full_name: str) -> Optional[Dict[str, Any]]:
        """Find existing repository by full name"""
        try:
            response = self._make_request(
                'GET',
                'objects/repos/records',
                params={
                    'filter[repo_full_name][eq]': repo_full_name,
                    'limit': 1
                }
            )

            records = response.get('data', [])
            if records:
                return records[0]
            return None

        except Exception as e:
            self.logger.warning(f"Error finding existing repo {repo_full_name}: {e}")
            return None

    def import_memberships(self, memberships_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Import membership data into Attio"""
        self.logger.info(f"Importing {len(memberships_data)} membership records")

        results = {
            'total': len(memberships_data),
            'successful': 0,
            'failed': 0,
            'errors': []
        }

        for membership in memberships_data:
            try:
                result = self._import_membership(membership)
                if result['success']:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append({
                        'record': membership.get('membership_id', 'unknown'),
                        'error': result['error']
                    })
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'record': membership.get('membership_id', 'unknown'),
                    'error': str(e)
                })

        self.logger.info(f"Membership import complete: {results['successful']}/{results['total']} successful")
        return results

    def _import_membership(self, membership: Dict[str, Any]) -> Dict[str, Any]:
        """Import a single membership record"""
        try:
            attio_data = self._transform_membership_for_attio(membership)

            # Check if membership already exists
            existing = self._find_existing_membership(membership['membership_id'])

            if existing:
                record_id = existing['id']['value']
                response = self._make_request(
                    'PUT',
                    f'objects/repo_membership/records/{record_id}',
                    attio_data
                )
            else:
                response = self._make_request(
                    'POST',
                    'objects/repo_membership/records',
                    attio_data
                )

            return {'success': True}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _transform_membership_for_attio(self, membership: Dict[str, Any]) -> Dict[str, Any]:
        """Transform membership data to Attio format"""
        attio_membership = {
            "data": {
                "membership_id": {"value": membership.get("membership_id")},
                "login": {"value": membership.get("login")},
                "repo_full_name": {"value": membership.get("repo_full_name")},
                "role": {"value": membership.get("role", "contributor")},
                "permission": {"value": membership.get("permission")},
                "contributions_past_year": {"value": membership.get("contributions_past_year")},
                "last_activity_at": {"value": membership.get("last_activity_at")}
            }
        }

        return attio_membership

    def _find_existing_membership(self, membership_id: str) -> Optional[Dict[str, Any]]:
        """Find existing membership by ID"""
        try:
            response = self._make_request(
                'GET',
                'objects/repo_membership/records',
                params={
                    'filter[membership_id][eq]': membership_id,
                    'limit': 1
                }
            )

            records = response.get('data', [])
            if records:
                return records[0]
            return None

        except Exception as e:
            self.logger.warning(f"Error finding existing membership {membership_id}: {e}")
            return None

    def import_signals(self, signals_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Import signal data into Attio"""
        self.logger.info(f"Importing {len(signals_data)} signal records")

        results = {
            'total': len(signals_data),
            'successful': 0,
            'failed': 0,
            'errors': []
        }

        for signal in signals_data:
            try:
                result = self._import_signal(signal)
                if result['success']:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append({
                        'record': signal.get('signal_id', 'unknown'),
                        'error': result['error']
                    })
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'record': signal.get('signal_id', 'unknown'),
                    'error': str(e)
                })

        self.logger.info(f"Signal import complete: {results['successful']}/{results['total']} successful")
        return results

    def _import_signal(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Import a single signal record"""
        try:
            attio_data = self._transform_signal_for_attio(signal)

            # Check if signal already exists
            existing = self._find_existing_signal(signal['signal_id'])

            if existing:
                record_id = existing['id']['value']
                response = self._make_request(
                    'PUT',
                    f'objects/signals/records/{record_id}',
                    attio_data
                )
            else:
                response = self._make_request(
                    'POST',
                    'objects/signals/records',
                    attio_data
                )

            return {'success': True}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _transform_signal_for_attio(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Transform signal data to Attio format"""
        attio_signal = {
            "data": {
                "signal_id": {"value": signal.get("signal_id")},
                "signal_type": {"value": signal.get("signal_type")},
                "signal": {"value": signal.get("signal")},
                "signal_at": {"value": signal.get("signal_at")},
                "url": {"value": signal.get("url")},
                "source": {"value": "GitHub"},
                "repo_full_name": {"value": signal.get("repo_full_name")},
                "login": {"value": signal.get("login")}
            }
        }

        return attio_signal

    def _find_existing_signal(self, signal_id: str) -> Optional[Dict[str, Any]]:
        """Find existing signal by ID"""
        try:
            response = self._make_request(
                'GET',
                'objects/signals/records',
                params={
                    'filter[signal_id][eq]': signal_id,
                    'limit': 1
                }
            )

            records = response.get('data', [])
            if records:
                return records[0]
            return None

        except Exception as e:
            self.logger.warning(f"Error finding existing signal {signal_id}: {e}")
            return None

    def import_intelligence_data(self, intelligence_data: Dict[str, Any]) -> Dict[str, Any]:
        """Import all intelligence data into Attio"""
        self.logger.info("Starting comprehensive Attio import")

        if not self.validate_connection():
            raise Exception("Attio API connection validation failed")

        results = {
            'timestamp': datetime.now().isoformat(),
            'people': {},
            'repos': {},
            'memberships': {},
            'signals': {},
            'overall': {}
        }

        try:
            # Import in order: repos first, then people, then relationships
            if 'repos' in intelligence_data:
                results['repos'] = self.import_repos(intelligence_data['repos'])

            if 'people' in intelligence_data:
                results['people'] = self.import_people(intelligence_data['people'])

            if 'memberships' in intelligence_data:
                results['memberships'] = self.import_memberships(intelligence_data['memberships'])

            if 'signals' in intelligence_data:
                results['signals'] = self.import_signals(intelligence_data['signals'])

            # Calculate overall statistics
            total_processed = sum(r.get('total', 0) for r in results.values() if isinstance(r, dict))
            total_successful = sum(r.get('successful', 0) for r in results.values() if isinstance(r, dict))
            total_failed = sum(r.get('failed', 0) for r in results.values() if isinstance(r, dict))

            results['overall'] = {
                'total_processed': total_processed,
                'total_successful': total_successful,
                'total_failed': total_failed,
                'success_rate': total_successful / total_processed if total_processed > 0 else 0
            }

            self.logger.info(f"Attio import complete: {total_successful}/{total_processed} successful")

        except Exception as e:
            self.logger.error(f"Attio import failed: {e}")
            results['overall']['error'] = str(e)

        return results

    def export_import_results(self, results: Dict[str, Any], output_path: str):
        """Export import results to file"""
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        self.logger.info(f"Import results exported to {output_path}")
