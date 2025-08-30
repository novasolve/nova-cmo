#!/usr/bin/env python3
"""
Quality Gates
Pre-campaign validation gates for prospect qualification
"""

from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass
import logging
import re

logger = logging.getLogger(__name__)


@dataclass
class QualityGateResult:
    """Result of quality gate validation"""
    passes_all_gates: bool
    gate_results: Dict[str, bool]
    failure_reasons: List[str]
    warnings: List[str]
    quality_score: float


class QualityGate:
    """Implements quality gates for prospect validation"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Quality gate thresholds
        self.gates = {
            'email_required': config.get('email_required', True),
            'email_deliverable': config.get('email_deliverable', True),
            'data_completeness': config.get('data_completeness_threshold', 0.8),
            'data_accuracy': config.get('data_accuracy_threshold', 0.7),
            'data_consistency': config.get('data_consistency_threshold', 0.9),
            'icp_relevance': config.get('icp_relevance_threshold', 0.6),
            'activity_recent': config.get('activity_recent_threshold', 90),  # days
            'compliance_pass': config.get('compliance_required', True),
            'personalization_ready': config.get('personalization_ready', True)
        }

    def validate_prospect(self, prospect: Dict[str, Any]) -> QualityGateResult:
        """
        Run all quality gates on a prospect
        Returns QualityGateResult with detailed validation results
        """
        gate_results = {}
        failure_reasons = []
        warnings = []
        quality_score = 0.0

        # Gate 1: Email validation
        email_result, email_reasons = self._validate_email_gate(prospect)
        gate_results['email'] = email_result
        if not email_result:
            failure_reasons.extend(email_reasons)

        # Gate 2: Data completeness
        completeness_result, completeness_score, completeness_reasons = self._validate_completeness_gate(prospect)
        gate_results['completeness'] = completeness_result
        quality_score += completeness_score * 0.25
        if not completeness_result:
            failure_reasons.extend(completeness_reasons)

        # Gate 3: Data accuracy
        accuracy_result, accuracy_score, accuracy_reasons = self._validate_accuracy_gate(prospect)
        gate_results['accuracy'] = accuracy_result
        quality_score += accuracy_score * 0.25
        if not accuracy_result:
            failure_reasons.extend(accuracy_reasons)

        # Gate 4: Data consistency
        consistency_result, consistency_score, consistency_reasons = self._validate_consistency_gate(prospect)
        gate_results['consistency'] = consistency_result
        quality_score += consistency_score * 0.25
        if not consistency_result:
            failure_reasons.extend(consistency_reasons)

        # Gate 5: ICP relevance
        icp_result, icp_score, icp_reasons = self._validate_icp_gate(prospect)
        gate_results['icp_relevance'] = icp_result
        quality_score += icp_score * 0.15
        if not icp_result:
            failure_reasons.extend(icp_reasons)

        # Gate 6: Activity recency
        activity_result, activity_reasons = self._validate_activity_gate(prospect)
        gate_results['activity'] = activity_result
        if not activity_result:
            failure_reasons.extend(activity_reasons)

        # Gate 7: Compliance
        compliance_result, compliance_reasons = self._validate_compliance_gate(prospect)
        gate_results['compliance'] = compliance_result
        if not compliance_result:
            failure_reasons.extend(compliance_reasons)

        # Gate 8: Personalization readiness
        personalization_result, personalization_reasons = self._validate_personalization_gate(prospect)
        gate_results['personalization'] = personalization_result
        if not personalization_result:
            failure_reasons.extend(personalization_reasons)

        # Overall result
        passes_all_gates = all(gate_results.values())

        # Generate warnings for borderline cases
        warnings = self._generate_warnings(prospect, gate_results)

        return QualityGateResult(
            passes_all_gates=passes_all_gates,
            gate_results=gate_results,
            failure_reasons=failure_reasons,
            warnings=warnings,
            quality_score=quality_score
        )

    def _validate_email_gate(self, prospect: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate email gate - must have valid email"""
        reasons = []

        # Check if email is required
        if not self.gates['email_required']:
            return True, []

        # Get email (prefer profile email over commit email)
        email = prospect.get('email_profile') or prospect.get('email_public_commit')

        if not email:
            return False, ["No email address found"]

        # Basic email format validation
        if not self._is_valid_email_format(email):
            return False, [f"Invalid email format: {email}"]

        # Check for disposable emails
        if self._is_disposable_email(email):
            return False, [f"Disposable email not allowed: {email}"]

        # Check for noreply emails
        if 'noreply' in email.lower() or 'users.noreply' in email.lower():
            return False, ["Noreply email not allowed"]

        # Domain validation if configured
        if self.gates['email_deliverable']:
            domain = email.split('@')[1].lower()
            if not self._is_deliverable_domain(domain):
                return False, [f"Undeliverable domain: {domain}"]

        return True, []

    def _validate_completeness_gate(self, prospect: Dict[str, Any]) -> Tuple[bool, float, List[str]]:
        """Validate data completeness"""
        reasons = []

        # Required fields for basic completeness
        required_fields = ['login', 'name', 'github_user_url']
        optional_fields = ['company', 'location', 'bio', 'followers', 'public_repos']

        present_required = sum(1 for field in required_fields if prospect.get(field))
        present_optional = sum(1 for field in optional_fields if prospect.get(field))

        total_fields = len(required_fields) + len(optional_fields)
        present_fields = present_required + present_optional

        completeness_score = present_fields / total_fields

        # Check required fields
        missing_required = [field for field in required_fields if not prospect.get(field)]
        if missing_required:
            reasons.append(f"Missing required fields: {', '.join(missing_required)}")

        # Overall completeness check
        if completeness_score < self.gates['data_completeness']:
            reasons.append(".2f")

        passes = completeness_score >= self.gates['data_completeness'] and present_required == len(required_fields)

        return passes, completeness_score, reasons

    def _validate_accuracy_gate(self, prospect: Dict[str, Any]) -> Tuple[bool, float, List[str]]:
        """Validate data accuracy"""
        reasons = []
        accuracy_score = 1.0  # Start with perfect score

        # Email accuracy
        email = prospect.get('email_profile') or prospect.get('email_public_commit')
        if email:
            # Check for common email issues
            if self._has_email_issues(email):
                accuracy_score -= 0.3
                reasons.append("Email has potential accuracy issues")

        # URL accuracy
        urls_to_check = ['github_user_url', 'github_repo_url', 'html_url']
        for url_field in urls_to_check:
            url = prospect.get(url_field)
            if url and not self._is_valid_url(url):
                accuracy_score -= 0.2
                reasons.append(f"Invalid URL in {url_field}")

        # Follower/following ratio sanity check
        followers = prospect.get('followers') or 0
        following = prospect.get('following') or 0
        if followers > 0 and following > followers * 5:
            accuracy_score -= 0.1
            reasons.append("Unusual follower/following ratio")

        passes = accuracy_score >= self.gates['data_accuracy']

        return passes, accuracy_score, reasons

    def _validate_consistency_gate(self, prospect: Dict[str, Any]) -> Tuple[bool, float, List[str]]:
        """Validate data consistency"""
        reasons = []
        consistency_score = 1.0

        # Login consistency with URLs
        login = prospect.get('login', '').lower()
        if login:
            user_url = prospect.get('github_user_url', '').lower()
            if user_url and login not in user_url:
                consistency_score -= 0.3
                reasons.append("Login not found in GitHub URL")

        # Repo name consistency
        repo_full_name = prospect.get('repo_full_name', '').lower()
        if repo_full_name:
            repo_url = prospect.get('github_repo_url', '').lower()
            if repo_url and repo_full_name not in repo_url:
                consistency_score -= 0.3
                reasons.append("Repo name not found in repo URL")

        # Name and bio consistency (basic check)
        name = prospect.get('name', '').lower()
        bio = prospect.get('bio', '').lower()
        if name and bio and len(name.split()) > 1:
            first_name = name.split()[0]
            if first_name not in bio:
                consistency_score -= 0.1
                reasons.append("Name not mentioned in bio")

        passes = consistency_score >= self.gates['data_consistency']

        return passes, consistency_score, reasons

    def _validate_icp_gate(self, prospect: Dict[str, Any]) -> Tuple[bool, float, List[str]]:
        """Validate ICP relevance"""
        reasons = []

        # Check if ICP relevance score is available
        icp_score = prospect.get('icp_relevance_score')
        if icp_score is None:
            return False, 0.0, ["ICP relevance not calculated"]

        passes = icp_score >= self.gates['icp_relevance']

        if not passes:
            reasons.append(".2f")

        return passes, icp_score, reasons

    def _validate_activity_gate(self, prospect: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate activity recency"""
        reasons = []

        # Check signal timestamp
        signal_at = prospect.get('signal_at')
        if not signal_at:
            return False, ["No activity timestamp"]

        # Calculate days since activity
        try:
            from datetime import datetime
            from .timezone_utils import parse_utc_datetime

            signal_date = parse_utc_datetime(signal_at)
            days_since = (datetime.now() - signal_date).days

            if days_since > self.gates['activity_recent']:
                return False, [f"Activity too old ({days_since} days)"]

        except Exception as e:
            return False, [f"Could not parse activity date: {e}"]

        return True, []

    def _validate_compliance_gate(self, prospect: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate compliance requirements"""
        reasons = []

        if not self.gates['compliance_pass']:
            return True, []

        # Check for compliance flags
        compliance_result = prospect.get('compliance_result')
        if compliance_result and isinstance(compliance_result, dict):
            if not compliance_result.get('compliant', True):
                reasons.append("Compliance check failed")
                risk_factors = compliance_result.get('risk_factors', [])
                if risk_factors:
                    reasons.extend([f"Risk factor: {factor}" for factor in risk_factors])

        # Email domain compliance
        email = prospect.get('email_profile') or prospect.get('email_public_commit')
        if email and '@' in email:
            domain = email.split('@')[1].lower()
            blocked_domains = self.config.get('blocked_email_domains', [])
            if domain in [d.lower() for d in blocked_domains]:
                reasons.append(f"Blocked email domain: {domain}")

        passes = len(reasons) == 0
        return passes, reasons

    def _validate_personalization_gate(self, prospect: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate personalization readiness"""
        reasons = []

        if not self.gates['personalization_ready']:
            return True, []

        # Must have basic personalization data
        required_for_personalization = ['name', 'repo_full_name']

        missing = [field for field in required_for_personalization if not prospect.get(field)]
        if missing:
            reasons.append(f"Missing personalization data: {', '.join(missing)}")

        # Must have signal for context
        if not prospect.get('signal'):
            reasons.append("Missing signal data for personalization")

        # Language should be known for technical personalization
        if not prospect.get('language'):
            reasons.append("Missing language data for technical personalization")

        passes = len(reasons) == 0
        return passes, reasons

    def _is_valid_email_format(self, email: str) -> bool:
        """Basic email format validation"""
        if not email or '@' not in email:
            return False

        # Simple regex check
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def _is_disposable_email(self, email: str) -> bool:
        """Check if email is from disposable provider"""
        domain = email.split('@')[1].lower()

        disposable_domains = {
            '10minutemail.com', 'guerrillamail.com', 'mailinator.com',
            'temp-mail.org', 'throwaway.email', 'yopmail.com'
        }

        return domain in disposable_domains

    def _is_deliverable_domain(self, domain: str) -> bool:
        """Check if domain is likely deliverable"""
        # This is a simplified check - in production you'd use MX record validation
        undeliverable_patterns = [
            'example.com', 'test.com', 'invalid.com',
            'localhost', '127.0.0.1'
        ]

        return domain not in undeliverable_patterns and '.' in domain

    def _has_email_issues(self, email: str) -> bool:
        """Check for common email accuracy issues"""
        issues = [
            'test' in email.lower(),
            'example' in email.lower(),
            'placeholder' in email.lower(),
            email.count('@') > 1,
            len(email) > 254,  # RFC 5321 limit
        ]

        return any(issues)

    def _is_valid_url(self, url: str) -> bool:
        """Basic URL validation"""
        if not url:
            return False

        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return bool(parsed.scheme and parsed.netloc)
        except:
            return False

    def _generate_warnings(self, prospect: Dict[str, Any], gate_results: Dict[str, bool]) -> List[str]:
        """Generate warnings for borderline cases"""
        warnings = []

        # Warning for low ICP relevance
        icp_score = prospect.get('icp_relevance_score', 0)
        if icp_score > 0.4 and icp_score < self.gates['icp_relevance']:
            warnings.append(".2f")

        # Warning for old activity
        signal_at = prospect.get('signal_at')
        if signal_at:
            try:
                from datetime import datetime
                from .timezone_utils import parse_utc_datetime

                signal_date = parse_utc_datetime(signal_at)
                days_since = (datetime.now() - signal_date).days

                if days_since > 60 and days_since <= self.gates['activity_recent']:
                    warnings.append(f"Activity is {days_since} days old (approaching threshold)")
            except:
                pass

        return warnings

    def validate_batch(self, prospects: List[Dict[str, Any]]) -> List[QualityGateResult]:
        """
        Validate a batch of prospects through quality gates
        Returns list of QualityGateResult objects
        """
        results = []

        for prospect in prospects:
            try:
                result = self.validate_prospect(prospect)
                results.append(result)
            except Exception as e:
                self.logger.warning(f"Quality gate validation failed for prospect {prospect.get('login', 'unknown')}: {e}")
                # Return failed result
                failed_result = QualityGateResult(
                    passes_all_gates=False,
                    gate_results={},
                    failure_reasons=[f"Validation error: {str(e)}"],
                    warnings=[],
                    quality_score=0.0
                )
                results.append(failed_result)

        return results

    def get_quality_stats(self, results: List[QualityGateResult]) -> Dict[str, Any]:
        """Get statistics about quality gate validation"""
        total_prospects = len(results)
        if total_prospects == 0:
            return {'total_prospects': 0}

        passing_prospects = sum(1 for r in results if r.passes_all_gates)

        # Gate-specific pass rates
        gate_stats = {}
        for gate_name in ['email', 'completeness', 'accuracy', 'consistency',
                         'icp_relevance', 'activity', 'compliance', 'personalization']:
            gate_passes = sum(1 for r in results if r.gate_results.get(gate_name, False))
            gate_stats[gate_name] = {
                'passed': gate_passes,
                'pass_rate': gate_passes / total_prospects
            }

        # Quality score distribution
        quality_scores = [r.quality_score for r in results]
        avg_quality = sum(quality_scores) / total_prospects

        return {
            'total_prospects': total_prospects,
            'passing_prospects': passing_prospects,
            'pass_rate': passing_prospects / total_prospects,
            'avg_quality_score': avg_quality,
            'gate_stats': gate_stats,
            'quality_distribution': self._calculate_quality_distribution(quality_scores)
        }

    def _calculate_quality_distribution(self, scores: List[float]) -> Dict[str, int]:
        """Calculate quality score distribution"""
        distribution = {'excellent': 0, 'good': 0, 'fair': 0, 'poor': 0}

        for score in scores:
            if score >= 0.9:
                distribution['excellent'] += 1
            elif score >= 0.7:
                distribution['good'] += 1
            elif score >= 0.5:
                distribution['fair'] += 1
            else:
                distribution['poor'] += 1

        return distribution
