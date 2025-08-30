#!/usr/bin/env python3
"""
Data Validation and Quality System
Ensures data integrity, completeness, and quality across the intelligence pipeline
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from email_validator import validate_email, EmailNotValidError
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class DataValidator:
    """Comprehensive data validation and quality assurance system"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        self.validation_errors = []
        self.quality_metrics = {}
        self.logger = logger

    def _default_config(self) -> Dict[str, Any]:
        """Default validation configuration"""
        return {
            'strict_mode': True,
            'public_email_domains': {
                'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
                'aol.com', 'proton.me', 'protonmail.com', 'icloud.com',
                'live.com', 'msn.com', 'yandex.com', 'mail.com'
            },
            'min_bio_length': 10,
            'max_bio_length': 500,
            'required_fields': {
                'people': ['login', 'github_user_url'],
                'repos': ['repo_full_name', 'html_url'],
                'signals': ['signal_id', 'signal_type', 'signal_at']
            },
            'email_validation': {
                'check_format': True,
                'check_deliverability': False,  # Can be expensive, optional
                'allow_noreply': False
            },
            'url_validation': {
                'check_format': True,
                'check_accessibility': False  # Can be slow, optional
            }
        }

    def validate_lead(self, lead: Dict[str, Any]) -> Tuple[bool, List[str], Dict[str, Any]]:
        """
        Comprehensive lead validation
        Returns: (is_valid, error_messages, quality_score)
        """
        errors = []
        quality_score = {
            'completeness': 0.0,
            'accuracy': 0.0,
            'consistency': 0.0,
            'overall': 0.0
        }

        # Required field validation
        required_fields = self.config['required_fields']['people']
        for field in required_fields:
            if not lead.get(field):
                errors.append(f"Missing required field: {field}")

        # Email validation
        email_quality = self._validate_emails(lead)
        if not email_quality['valid']:
            errors.extend(email_quality['errors'])

        # URL validation
        url_quality = self._validate_urls(lead)
        if not url_quality['valid']:
            errors.extend(url_quality['errors'])

        # Data consistency validation
        consistency_issues = self._validate_consistency(lead)
        errors.extend(consistency_issues)

        # Quality scoring
        quality_score = self._calculate_quality_score(lead, email_quality, url_quality)

        is_valid = len(errors) == 0 and quality_score['overall'] >= 0.6
        return is_valid, errors, quality_score

    def _validate_emails(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Validate email addresses"""
        result = {
            'valid': True,
            'errors': [],
            'quality_score': 0.0,
            'corporate_emails': [],
            'personal_emails': []
        }

        emails = []
        if lead.get('email_profile'):
            emails.append(('email_profile', lead['email_profile']))
        if lead.get('email_public_commit'):
            emails.append(('email_public_commit', lead['email_public_commit']))

        if not emails:
            result['errors'].append("No email addresses found")
            result['valid'] = False
            return result

        for field_name, email in emails:
            # Basic format validation
            if not self._is_valid_email_format(email):
                result['errors'].append(f"Invalid email format in {field_name}: {email}")
                result['valid'] = False
                continue

            # Check for noreply emails
            if 'noreply' in email.lower() or 'users.noreply' in email.lower():
                if not self.config['email_validation']['allow_noreply']:
                    result['errors'].append(f"Noreply email not allowed: {email}")
                    result['valid'] = False
                    continue

            # Categorize email type
            domain = email.split('@')[1].lower()
            if domain in self.config['public_email_domains']:
                result['personal_emails'].append(email)
            else:
                result['corporate_emails'].append(email)

        # Quality scoring
        if result['corporate_emails']:
            result['quality_score'] = 1.0  # Corporate emails are highest quality
        elif result['personal_emails']:
            result['quality_score'] = 0.7  # Personal emails are acceptable
        else:
            result['quality_score'] = 0.3  # Only noreply or invalid emails

        return result

    def _validate_urls(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """Validate URL fields"""
        result = {
            'valid': True,
            'errors': [],
            'quality_score': 0.0
        }

        url_fields = ['github_user_url', 'html_url', 'api_url', 'avatar_url']

        for field in url_fields:
            url = lead.get(field)
            if url:
                if not self._is_valid_url(url):
                    result['errors'].append(f"Invalid URL format in {field}: {url}")
                    result['valid'] = False

        # Quality scoring based on URL completeness
        valid_urls = sum(1 for field in url_fields if lead.get(field) and self._is_valid_url(lead[field]))
        result['quality_score'] = valid_urls / len(url_fields)

        return result

    def _validate_consistency(self, lead: Dict[str, Any]) -> List[str]:
        """Check data consistency across fields"""
        errors = []

        # Login consistency with URLs
        login = lead.get('login')
        if login:
            user_url = lead.get('github_user_url', '')
            if user_url and login not in user_url:
                errors.append(f"Login '{login}' not found in GitHub URL: {user_url}")

        # Repo name consistency
        repo_full_name = lead.get('repo_full_name')
        if repo_full_name:
            user_url = lead.get('github_repo_url', '')
            if user_url and repo_full_name not in user_url:
                errors.append(f"Repo name '{repo_full_name}' not found in repo URL: {user_url}")

        # Follower/following ratio (basic sanity check)
        followers = lead.get('followers') or 0
        following = lead.get('following') or 0
        if followers > 0 and following > followers * 10:
            errors.append(f"Unusual follower/following ratio: {followers}/{following}")

        # Stars validation
        stars = lead.get('stars') or 0
        if stars < 0:
            errors.append(f"Negative stars count: {stars}")

        return errors

    def _calculate_quality_score(self, lead: Dict[str, Any], email_quality: Dict, url_quality: Dict) -> Dict[str, float]:
        """Calculate overall data quality score"""
        scores = {
            'completeness': 0.0,
            'accuracy': 0.0,
            'consistency': 0.0,
            'overall': 0.0
        }

        # Completeness score (required fields present)
        required_fields = ['login', 'name', 'company', 'location', 'bio', 'followers', 'public_repos']
        present_fields = sum(1 for field in required_fields if lead.get(field) is not None and lead[field] != '')
        scores['completeness'] = present_fields / len(required_fields)

        # Accuracy score (based on email and URL validation)
        scores['accuracy'] = (email_quality['quality_score'] + url_quality['quality_score']) / 2

        # Consistency score (no validation errors)
        consistency_errors = self._validate_consistency(lead)
        scores['consistency'] = max(0, 1 - (len(consistency_errors) * 0.1))

        # Overall score (weighted average)
        weights = {'completeness': 0.3, 'accuracy': 0.4, 'consistency': 0.3}
        scores['overall'] = sum(scores[comp] * weight for comp, weight in weights.items())

        return scores

    def _is_valid_email_format(self, email: str) -> bool:
        """Check basic email format"""
        if not email or '@' not in email:
            return False

        try:
            validate_email(email, check_deliverability=False)
            return True
        except EmailNotValidError:
            return False

    def _is_valid_url(self, url: str) -> bool:
        """Check basic URL format"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False

    def validate_batch(self, leads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate a batch of leads and return comprehensive statistics"""
        results = {
            'total_leads': len(leads),
            'valid_leads': 0,
            'invalid_leads': 0,
            'quality_distribution': {
                'excellent': 0,  # >= 0.9
                'good': 0,       # >= 0.7
                'fair': 0,       # >= 0.5
                'poor': 0        # < 0.5
            },
            'common_errors': {},
            'quality_metrics': {
                'avg_completeness': 0.0,
                'avg_accuracy': 0.0,
                'avg_consistency': 0.0,
                'avg_overall': 0.0
            }
        }

        all_completeness = []
        all_accuracy = []
        all_consistency = []
        all_overall = []

        for lead in leads:
            is_valid, errors, quality_score = self.validate_lead(lead)

            if is_valid:
                results['valid_leads'] += 1
            else:
                results['invalid_leads'] += 1

            # Categorize quality
            overall = quality_score['overall']
            if overall >= 0.9:
                results['quality_distribution']['excellent'] += 1
            elif overall >= 0.7:
                results['quality_distribution']['good'] += 1
            elif overall >= 0.5:
                results['quality_distribution']['fair'] += 1
            else:
                results['quality_distribution']['poor'] += 1

            # Track errors
            for error in errors:
                results['common_errors'][error] = results['common_errors'].get(error, 0) + 1

            # Accumulate quality scores
            all_completeness.append(quality_score['completeness'])
            all_accuracy.append(quality_score['accuracy'])
            all_consistency.append(quality_score['consistency'])
            all_overall.append(quality_score['overall'])

        # Calculate averages (avoid division by zero)
        total_leads = len(leads)
        if total_leads > 0:
            results['quality_metrics']['avg_completeness'] = sum(all_completeness) / total_leads if all_completeness else 0.0
            results['quality_metrics']['avg_accuracy'] = sum(all_accuracy) / total_leads if all_accuracy else 0.0
            results['quality_metrics']['avg_consistency'] = sum(all_consistency) / total_leads if all_consistency else 0.0
            results['quality_metrics']['avg_overall'] = sum(all_overall) / total_leads if all_overall else 0.0
        else:
            results['quality_metrics']['avg_completeness'] = 0.0
            results['quality_metrics']['avg_accuracy'] = 0.0
            results['quality_metrics']['avg_consistency'] = 0.0
            results['quality_metrics']['avg_overall'] = 0.0

        return results

    def generate_quality_report(self, validation_results: Dict[str, Any]) -> str:
        """Generate a human-readable quality report"""
        report = []
        report.append("# Data Quality Report")
        report.append(f"Generated: {datetime.now().isoformat()}")
        report.append("")

        report.append("## Summary Statistics")
        total_leads = validation_results['total_leads']
        report.append(f"- Total Leads: {total_leads}")
        if total_leads > 0:
            valid_pct = validation_results['valid_leads'] / total_leads * 100
            invalid_pct = validation_results['invalid_leads'] / total_leads * 100
            report.append(f"- Valid Leads: {validation_results['valid_leads']} ({valid_pct:.1f}%)")
            report.append(f"- Invalid Leads: {validation_results['invalid_leads']} ({invalid_pct:.1f}%)")
        else:
            report.append("- Valid Leads: 0 (0.0%)")
            report.append("- Invalid Leads: 0 (0.0%)")
        report.append("")

        report.append("## Quality Distribution")
        total_leads = validation_results['total_leads']
        if total_leads > 0:
            for category, count in validation_results['quality_distribution'].items():
                percentage = count / total_leads * 100
                report.append(f"- {category.capitalize()}: {count} ({percentage:.1f}%)")
        else:
            report.append("- No leads to analyze")
        report.append("")

        report.append("## Average Quality Scores")
        metrics = validation_results['quality_metrics']
        report.append(f"- Completeness: {metrics['avg_completeness']:.2f}")
        report.append(f"- Accuracy: {metrics['avg_accuracy']:.2f}")
        report.append(f"- Consistency: {metrics['avg_consistency']:.2f}")
        report.append(f"- Overall: {metrics['avg_overall']:.2f}")
        report.append("")

        if validation_results['common_errors']:
            report.append("## Most Common Issues")
            sorted_errors = sorted(validation_results['common_errors'].items(),
                                 key=lambda x: x[1], reverse=True)[:10]
            for error, count in sorted_errors:
                percentage = count / validation_results['total_leads'] * 100
                report.append(f"- {error}: {count} ({percentage:.1f}%)")
            report.append("")

        return "\n".join(report)

    def export_validation_results(self, results: Dict[str, Any], output_path: str):
        """Export validation results to JSON"""
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        self.logger.info(f"Validation results exported to {output_path}")
