#!/usr/bin/env python3
"""
Lead Scoring Model
Calculates priority scores and deliverability risk for lead qualification
"""

import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LeadScore:
    """Complete lead scoring result"""
    priority_score: float
    deliverability_risk: float
    component_scores: Dict[str, float]
    risk_factors: List[str]
    priority_signals: List[str]
    cohort: Dict[str, str]
    recommendation: str


class LeadScorer:
    """Scores leads based on product fit and deliverability risk"""

    def __init__(self):
        self.scoring_weights = {
            'recency': 0.35,
            'stars_bucket': 0.20,
            'ci_flake_score': 0.25,
            'patchability_score': 0.20
        }

        self.risk_weights = {
            'role_email': 0.35,
            'domain_age': 0.25,
            'mx_validity': 0.20,
            'reputation': 0.20
        }

    def score_lead(self, lead: Dict[str, Any], enrichment: Dict[str, Any]) -> LeadScore:
        """
        Calculate comprehensive lead score
        """
        # Calculate priority score (product fit)
        priority_score = self._calculate_priority_score(lead, enrichment)

        # Calculate deliverability risk
        deliverability_risk = self._calculate_deliverability_risk(lead)

        # Extract component scores
        component_scores = self._extract_component_scores(lead, enrichment)

        # Identify risk factors and priority signals
        risk_factors = self._identify_risk_factors(lead, deliverability_risk)
        priority_signals = self._identify_priority_signals(lead, enrichment, priority_score)

        # Determine cohort
        cohort = self._determine_cohort(lead, enrichment)

        # Generate recommendation
        recommendation = self._generate_recommendation(priority_score, deliverability_risk, cohort)

        return LeadScore(
            priority_score=round(priority_score, 3),
            deliverability_risk=round(deliverability_risk, 3),
            component_scores=component_scores,
            risk_factors=risk_factors,
            priority_signals=priority_signals,
            cohort=cohort,
            recommendation=recommendation
        )

    def _calculate_priority_score(self, lead: Dict[str, Any], enrichment: Dict[str, Any]) -> float:
        """Calculate priority score based on product fit"""
        scores = {}

        # Recency score (last commit age)
        last_commit_age = enrichment.get('activity', {}).get('last_commit_age_days')
        scores['recency'] = self._score_recency(last_commit_age)

        # Stars bucket score
        stars = lead.get('stars', 0) or enrichment.get('stars', 0)
        scores['stars_bucket'] = self._score_stars_bucket(stars)

        # CI flake score
        scores['ci_flake_score'] = self._calculate_ci_flake_score(enrichment)

        # Patchability score
        scores['patchability_score'] = self._calculate_patchability_score(enrichment)

        # Calculate weighted priority score
        priority_score = sum(
            scores[component] * self.scoring_weights[component]
            for component in scores.keys()
        )

        return min(priority_score, 1.0)  # Cap at 1.0

    def _score_recency(self, days_since_commit: Optional[int]) -> float:
        """Score based on recency of last commit"""
        if days_since_commit is None:
            return 0.2  # Default for unknown

        if days_since_commit <= 14:
            return 1.0
        elif days_since_commit <= 30:
            return 0.8
        elif days_since_commit <= 90:
            return 0.5
        else:
            return 0.2

    def _score_stars_bucket(self, stars: int) -> float:
        """Score based on repository star count"""
        if stars < 1000:
            return 0.6
        elif stars <= 5000:
            return 0.8
        elif stars <= 20000:
            return 1.0
        else:
            return 0.7  # Conservative for very popular repos

    def _calculate_ci_flake_score(self, enrichment: Dict[str, Any]) -> float:
        """Calculate CI flake score based on failure patterns and keywords"""
        ci_data = enrichment.get('ci', {})
        score = 0.0

        # Base score from failure rate
        fail_rate = ci_data.get('fail_rate_30d', 0.0)
        if fail_rate > 0.5:
            score += 0.4
        elif fail_rate > 0.2:
            score += 0.6
        elif fail_rate > 0.1:
            score += 0.8

        # Bonus for flake hints
        flake_hints = ci_data.get('flake_hints', [])
        if flake_hints:
            score += min(len(flake_hints) * 0.1, 0.3)

        # Bonus for failing PRs
        pr_data = enrichment.get('prs', {})
        failing_prs = pr_data.get('with_failing_checks', 0)
        if failing_prs > 0:
            score += min(failing_prs * 0.1, 0.3)

        return min(score, 1.0)

    def _calculate_patchability_score(self, enrichment: Dict[str, Any]) -> float:
        """Calculate how patchable the repository is"""
        score = 0.0

        # Test framework presence
        test_data = enrichment.get('tests', {})
        if test_data.get('has_tests'):
            score += 0.3
            framework = test_data.get('framework')
            if framework in ['pytest', 'jest', 'go_test']:
                score += 0.2  # Preferred frameworks

        # Workflow simplicity (fewer workflows = simpler = more patchable)
        ci_data = enrichment.get('ci', {})
        workflows = ci_data.get('workflows', [])
        if len(workflows) <= 2:
            score += 0.2
        elif len(workflows) <= 5:
            score += 0.1

        # Language preference (Python/JS easier to patch)
        languages = enrichment.get('languages', [])
        if languages:
            primary_lang = languages[0].lower()
            if primary_lang in ['python', 'javascript', 'typescript']:
                score += 0.3
            elif primary_lang in ['go', 'rust']:
                score += 0.2

        return min(score, 1.0)

    def _calculate_deliverability_risk(self, lead: Dict[str, Any]) -> float:
        """Calculate deliverability risk score"""
        risk_score = 0.0

        # Role email check
        email = lead.get('email', '')
        if self._is_role_email(email):
            risk_score += self.risk_weights['role_email']

        # Domain analysis would require additional API calls
        # For now, we'll use basic heuristics
        domain = self._extract_domain(email)
        if domain:
            # Generic domains are riskier
            if domain in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']:
                risk_score += 0.2

            # Very short domains might be suspicious
            if len(domain.split('.')[0]) <= 2:
                risk_score += 0.1

        return min(risk_score, 1.0)

    def _is_role_email(self, email: str) -> bool:
        """Check if email is a role-based address"""
        if not email:
            return False

        role_patterns = [
            r'^admin@', r'^info@', r'^contact@', r'^support@',
            r'^hello@', r'^team@', r'^noreply@', r'^no-reply@',
            r'^postmaster@', r'^abuse@'
        ]

        email_lower = email.lower()
        return any(re.match(pattern, email_lower) for pattern in role_patterns)

    def _extract_domain(self, email: str) -> Optional[str]:
        """Extract domain from email address"""
        if '@' in email:
            return email.split('@')[1].lower()
        return None

    def _extract_component_scores(self, lead: Dict[str, Any], enrichment: Dict[str, Any]) -> Dict[str, float]:
        """Extract individual component scores for transparency"""
        return {
            'recency_score': self._score_recency(
                enrichment.get('activity', {}).get('last_commit_age_days')
            ),
            'stars_score': self._score_stars_bucket(
                lead.get('stars', 0) or enrichment.get('stars', 0)
            ),
            'ci_flake_score': self._calculate_ci_flake_score(enrichment),
            'patchability_score': self._calculate_patchability_score(enrichment)
        }

    def _identify_risk_factors(self, lead: Dict[str, Any], risk_score: float) -> List[str]:
        """Identify specific risk factors"""
        factors = []

        email = lead.get('email', '')
        if self._is_role_email(email):
            factors.append('role_email')

        if risk_score > 0.5:
            factors.append('high_deliverability_risk')

        domain = self._extract_domain(email)
        if domain in ['gmail.com', 'yahoo.com', 'hotmail.com']:
            factors.append('public_email_domain')

        return factors

    def _identify_priority_signals(self, lead: Dict[str, Any], enrichment: Dict[str, Any],
                                 priority_score: float) -> List[str]:
        """Identify positive priority signals"""
        signals = []

        if priority_score > 0.7:
            signals.append('high_product_fit')

        # CI flake signals
        ci_data = enrichment.get('ci', {})
        if ci_data.get('fail_rate_30d', 0) > 0.2:
            signals.append('ci_failures_detected')

        if ci_data.get('flake_hints'):
            signals.append('flake_indicators_present')

        # Test framework signals
        test_data = enrichment.get('tests', {})
        if test_data.get('has_tests'):
            signals.append('testing_framework_present')

        # Activity signals
        activity = enrichment.get('activity', {})
        if activity.get('commits_30d', 0) > 10:
            signals.append('high_recent_activity')

        return signals

    def _determine_cohort(self, lead: Dict[str, Any], enrichment: Dict[str, Any]) -> Dict[str, str]:
        """Determine lead cohort for personalization"""
        # Stars bucket
        stars = lead.get('stars', 0) or enrichment.get('stars', 0)
        if stars < 1000:
            stars_bucket = '<1k'
        elif stars <= 5000:
            stars_bucket = '1k-5k'
        elif stars <= 20000:
            stars_bucket = '5k-20k'
        else:
            stars_bucket = '>20k'

        # Recency bucket
        last_commit_age = enrichment.get('activity', {}).get('last_commit_age_days')
        if last_commit_age is None:
            recency_bucket = 'unknown'
        elif last_commit_age <= 30:
            recency_bucket = '≤30d'
        elif last_commit_age <= 90:
            recency_bucket = '≤90d'
        elif last_commit_age <= 180:
            recency_bucket = '≤180d'
        else:
            recency_bucket = '>180d'

        # Language
        languages = enrichment.get('languages', [])
        primary_lang = languages[0] if languages else lead.get('language', 'unknown')

        # CI provider
        ci_data = enrichment.get('ci', {})
        ci_provider = ci_data.get('provider', 'none')
        if ci_provider == 'github_actions':
            ci_provider = 'gha'

        return {
            'stars_bucket': stars_bucket,
            'recency': recency_bucket,
            'lang': primary_lang.lower(),
            'ci': ci_provider
        }

    def _generate_recommendation(self, priority_score: float, risk_score: float,
                               cohort: Dict[str, str]) -> str:
        """Generate recommendation for lead"""
        if risk_score > 0.5:
            return 'high_risk_skip'

        if priority_score > 0.8:
            return 'priority_send'

        if priority_score > 0.6:
            return 'normal_send'

        if priority_score > 0.4:
            return 'low_priority_send'

        return 'low_fit_skip'
