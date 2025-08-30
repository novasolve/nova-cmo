#!/usr/bin/env python3
"""
Prospect Scorer
Implements scoring and tiering logic for lead qualification
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import yaml
import os

from .compliance_checker import ComplianceChecker, ComplianceResult


@dataclass
class ScoringResult:
    """Result of prospect scoring"""
    total_score: int
    component_scores: Dict[str, int]
    tier: str
    recommendation: str
    risk_factors: List[str]
    priority_signals: List[str]
    cohort: Dict[str, Any]
    compliance_result: Optional[ComplianceResult] = None


class ProspectScorer:
    """Scores prospects based on multiple criteria and assigns tiers"""

    def __init__(self, icp_config_path: Optional[str] = None):
        self.icp_config = self._load_icp_config(icp_config_path)
        self.scoring_weights = self.icp_config.get('scoring_weights', {
            'maintainer': 35,
            'org_member': 25,
            'contactable': 20,
            'icp_match': 15,
            'stars_velocity': 5,
            'university_penalty': -15,
            'off_icp_penalty': -40
        })

        # Ensure scoring weights are integers (YAML can load them as strings)
        for key in self.scoring_weights:
            if isinstance(self.scoring_weights[key], str):
                self.scoring_weights[key] = int(self.scoring_weights[key])

        self.tier_thresholds = self.icp_config.get('tier_thresholds', {
            'A': 70,
            'B': 55,
            'C': 40,
            'REJECT': 0
        })

        # Ensure tier thresholds are integers (YAML can load them as strings)
        for key in self.tier_thresholds:
            if isinstance(self.tier_thresholds[key], str):
                self.tier_thresholds[key] = int(self.tier_thresholds[key])

        # Initialize compliance checker
        self.compliance_checker = ComplianceChecker(self.icp_config)

    def _load_icp_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load ICP configuration"""
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    return yaml.safe_load(f) or {}
            except Exception as e:
                print(f"⚠️  Failed to load ICP config: {e}")

        # Default configuration
        return {
            'scoring_weights': {
                'maintainer': 35,
                'org_member': 25,
                'contactable': 20,
                'icp_match': 15,
                'stars_velocity': 5,
                'university_penalty': -15,
                'off_icp_penalty': -40
            },
            'tier_thresholds': {
                'A': 70,
                'B': 55,
                'C': 40,
                'REJECT': 0
            }
        }

    def score_prospect(self, prospect_data: Dict[str, Any], repo_data: Optional[Dict[str, Any]] = None) -> ScoringResult:
        """Score a prospect and determine tier"""
        component_scores = {}
        risk_factors = []
        priority_signals = []

        # First, check compliance
        compliance_result = self.compliance_checker.check_compliance(prospect_data)

        # If blocked by compliance, force REJECT tier
        if self.compliance_checker.should_block_prospect(compliance_result):
            return ScoringResult(
                total_score=0,
                component_scores={'compliance_blocked': -100},
                tier='REJECT',
                recommendation="Blocked by compliance policy",
                risk_factors=compliance_result.risk_factors,
                priority_signals=[],
                cohort=self._determine_cohort(prospect_data, repo_data),
                compliance_result=compliance_result
            )

        # 1. Maintainer status score
        maintainer_score = self._score_maintainer_status(prospect_data)
        component_scores['maintainer'] = maintainer_score

        # 2. Organization membership score
        org_score = self._score_org_membership(prospect_data)
        component_scores['org_member'] = org_score

        # 3. Contactability score
        contactability_score = self._score_contactability(prospect_data)
        component_scores['contactable'] = contactability_score

        # 4. ICP match score
        icp_score = self._score_icp_match(prospect_data, repo_data)
        component_scores['icp_match'] = icp_score

        # 5. Activity/velocity score
        activity_score = self._score_activity(prospect_data, repo_data)
        component_scores['activity'] = activity_score

        # 6. Apply penalties
        penalties = self._calculate_penalties(prospect_data, repo_data)
        component_scores['penalties'] = penalties

        # 7. Apply compliance-based adjustments
        compliance_adjustment = self._calculate_compliance_adjustment(compliance_result)
        component_scores['compliance'] = compliance_adjustment

        # Calculate total score
        total_score = sum(component_scores.values())

        # Determine tier
        tier = self._determine_tier(total_score)

        # Generate recommendation
        recommendation = self._generate_recommendation(tier, prospect_data)

        # Identify risk factors (combine scoring and compliance risks)
        scoring_risks = self._identify_risk_factors(prospect_data, component_scores)
        risk_factors = list(set(scoring_risks + compliance_result.risk_factors))

        # Identify priority signals
        priority_signals = self._identify_priority_signals(prospect_data, component_scores)

        # Determine cohort
        cohort = self._determine_cohort(prospect_data, repo_data)

        return ScoringResult(
            total_score=total_score,
            component_scores=component_scores,
            tier=tier,
            recommendation=recommendation,
            risk_factors=risk_factors,
            priority_signals=priority_signals,
            cohort=cohort,
            compliance_result=compliance_result
        )

    def _score_maintainer_status(self, prospect: Dict[str, Any]) -> int:
        """Score based on maintainer status"""
        score = 0

        if prospect.get('is_maintainer', False):
            score += self.scoring_weights['maintainer']

        if prospect.get('is_codeowner', False):
            score += 10  # Bonus for CODEOWNERS

        permission_level = prospect.get('permission_level', 'read')
        if permission_level in ['admin', 'maintain']:
            score += 5  # Additional bonus for high permissions

        return score

    def _score_org_membership(self, prospect: Dict[str, Any]) -> int:
        """Score based on organization membership"""
        if prospect.get('is_org_member', False):
            return self.scoring_weights['org_member']
        return 0

    def _score_contactability(self, prospect: Dict[str, Any]) -> int:
        """Score based on contactability"""
        score = 0
        contactability_score = prospect.get('contactability_score', 0)

        # Convert contactability score to weighted component
        if contactability_score >= 80:
            score = self.scoring_weights['contactable']
        elif contactability_score >= 60:
            score = int(self.scoring_weights['contactable'] * 0.75)
        elif contactability_score >= 40:
            score = int(self.scoring_weights['contactable'] * 0.5)
        elif contactability_score >= 20:
            score = int(self.scoring_weights['contactable'] * 0.25)

        return score

    def _score_icp_match(self, prospect: Dict[str, Any], repo_data: Optional[Dict[str, Any]]) -> int:
        """Score based on ICP match"""
        score = 0

        # Language match
        prospect_lang = prospect.get('language', '')
        if prospect_lang:
            prospect_lang = prospect_lang.lower()
        icp_languages = self.icp_config.get('languages', [])
        if prospect_lang and prospect_lang in [lang.lower() for lang in icp_languages]:
            score += 5

        # Topic match
        topics = prospect.get('topics', '')
        if topics:
            topics = topics.lower()
        icp_topics = self.icp_config.get('include_topics', [])
        topic_matches = sum(1 for topic in icp_topics if topic.lower() in topics)
        if topic_matches > 0:
            score += min(topic_matches * 3, 10)  # Max 10 points for topics

        # Company whitelist match
        company = prospect.get('company', '')
        if company:
            company = company.lower()
        company_whitelist = self.icp_config.get('company_whitelist', [])
        if company and any(whitelisted.lower() in company for whitelisted in company_whitelist):
            score += 5

        return min(score, self.scoring_weights['icp_match'])

    def _score_activity(self, prospect: Dict[str, Any], repo_data: Optional[Dict[str, Any]]) -> int:
        """Score based on activity and repository quality"""
        score = 0

        # Stars bonus
        stars = prospect.get('stars', 0)
        if stars is not None:
            stars = int(stars) if isinstance(stars, str) else stars
        else:
            stars = 0

        if stars >= 300:
            score += self.scoring_weights['stars_velocity']
        elif stars >= 100:
            score += int(self.scoring_weights['stars_velocity'] * 0.5)

        # Commit velocity bonus
        commit_count_90d = prospect.get('commit_count_90d', 0)
        if commit_count_90d and commit_count_90d >= 5:
            score += int(self.scoring_weights['stars_velocity'] * 0.5)

        # Recent contributions
        contributions_last_year = prospect.get('contributions_last_year', 0)
        if contributions_last_year >= 50:
            score += 3
        elif contributions_last_year >= 10:
            score += 2

        return score

    def _calculate_penalties(self, prospect: Dict[str, Any], repo_data: Optional[Dict[str, Any]]) -> int:
        """Calculate penalties that reduce the score"""
        penalties = 0

        # University penalty
        if self._is_university_account(prospect):
            penalties += self.scoring_weights['university_penalty']

        # Off-ICP topic penalty
        if self._has_off_icp_topics(prospect):
            penalties += self.scoring_weights['off_icp_penalty']

        # Disposable email penalty
        if prospect.get('is_disposable_email', False):
            penalties -= 10

        # Low activity penalty
        if prospect.get('contributions_last_year', 0) < 5:
            penalties -= 5

        return penalties

    def _calculate_compliance_adjustment(self, compliance_result: ComplianceResult) -> int:
        """Calculate score adjustment based on compliance result"""
        if not compliance_result.compliant:
            # Apply penalties based on risk level
            if compliance_result.risk_level == 'high':
                return -20
            elif compliance_result.risk_level == 'medium':
                return -10
            else:
                return -5

        # Small bonus for fully compliant prospects
        return 5

    def _is_university_account(self, prospect: Dict[str, Any]) -> bool:
        """Check if account appears to be university/academic"""
        # Check email domain
        email = prospect.get('email_profile') or prospect.get('email_public_commit')
        if email and '@' in email:
            domain = email.split('@')[1].lower()
            academic_domains = self.icp_config.get('academic_domains', ['.edu', '.ac.uk', '.edu.cn'])
            if any(academic_suffix in domain for academic_suffix in academic_domains):
                return True

        # Check company field for academic indicators
        company = prospect.get('company', '')
        if company:
            company = company.lower()
        academic_keywords = ['university', 'college', 'institute', 'school', 'academy', 'research', 'lab']
        if company and any(keyword in company for keyword in academic_keywords):
            return True

        # Check bio for academic indicators
        bio = prospect.get('bio', '')
        if bio:
            bio = bio.lower()
        if any(keyword in bio for keyword in academic_keywords):
            return True

        return False

    def _has_off_icp_topics(self, prospect: Dict[str, Any]) -> bool:
        """Check if prospect has off-ICP topics"""
        topics = prospect.get('topics', '')
        if topics:
            topics = topics.lower()
        exclude_topics = self.icp_config.get('exclude_topics', [])

        return any(topic.lower() in topics for topic in exclude_topics)

    def _determine_tier(self, total_score: int) -> str:
        """Determine tier based on total score"""
        if total_score >= self.tier_thresholds['A']:
            return 'A'
        elif total_score >= self.tier_thresholds['B']:
            return 'B'
        elif total_score >= self.tier_thresholds['C']:
            return 'C'
        else:
            return 'REJECT'

    def _generate_recommendation(self, tier: str, prospect: Dict[str, Any]) -> str:
        """Generate recommendation based on tier and prospect data"""
        if tier == 'REJECT':
            return "Do not pursue - low quality or off-target"
        elif tier == 'C':
            return "Low priority - monitor for future engagement"
        elif tier == 'B':
            return "Medium priority - consider outreach after A-tier prospects"
        elif tier == 'A':
            login = prospect.get('login', 'unknown')
            maintainer_status = "maintainer" if prospect.get('is_maintainer') else "contributor"
            contactable = "contactable" if prospect.get('contactability_score', 0) > 50 else "needs enrichment"
            return f"High priority {maintainer_status} - {contactable} - pursue immediately"

        return "Review manually"

    def _identify_risk_factors(self, prospect: Dict[str, Any], component_scores: Dict[str, int]) -> List[str]:
        """Identify risk factors that could affect success"""
        risks = []

        # Contactability risks
        if prospect.get('contactability_score', 0) < 30:
            risks.append("low_contactability")

        if prospect.get('is_disposable_email', False):
            risks.append("disposable_email")

        # Academic/university risk
        if self._is_university_account(prospect):
            risks.append("academic_account")

        # Low activity risk
        if prospect.get('contributions_last_year', 0) < 10:
            risks.append("low_activity")

        # Off-ICP content risk
        if self._has_off_icp_topics(prospect):
            risks.append("off_icp_topics")

        # No maintainer status
        if not prospect.get('is_maintainer', False):
            risks.append("not_maintainer")

        return risks

    def _identify_priority_signals(self, prospect: Dict[str, Any], component_scores: Dict[str, int]) -> List[str]:
        """Identify positive signals that indicate high priority"""
        signals = []

        # High contactability
        if prospect.get('contactability_score', 0) >= 70:
            signals.append("high_contactability")

        # Maintainer status
        if prospect.get('is_maintainer', False):
            signals.append("maintainer")

        if prospect.get('is_codeowner', False):
            signals.append("codeowner")

        # Organization member
        if prospect.get('is_org_member', False):
            signals.append("org_member")

        # High activity
        if prospect.get('contributions_last_year', 0) >= 50:
            signals.append("high_activity")

        # ICP company match
        company = prospect.get('company', '').lower()
        company_whitelist = self.icp_config.get('company_whitelist', [])
        if company and any(whitelisted.lower() in company for whitelisted in company_whitelist):
            signals.append("icp_company_match")

        # Popular repository
        if prospect.get('stars', 0) >= 500:
            signals.append("popular_repo")

        return signals

    def _determine_cohort(self, prospect: Dict[str, Any], repo_data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Determine cohort characteristics for personalization"""
        cohort = {
            'stars_bucket': 'unknown',
            'tech_stack': 'unknown',
            'company_type': 'unknown',
            'activity_level': 'unknown'
        }

        # Stars bucket
        stars = prospect.get('stars', 0)
        if stars >= 1000:
            cohort['stars_bucket'] = 'large'
        elif stars >= 100:
            cohort['stars_bucket'] = 'medium'
        else:
            cohort['stars_bucket'] = 'small'

        # Tech stack
        language = prospect.get('language', '').lower()
        if language:
            cohort['tech_stack'] = language

        # Company type inference
        company = prospect.get('company', '').lower()
        if company:
            if any(term in company for term in ['inc', 'llc', 'corp', 'ltd']):
                cohort['company_type'] = 'corporate'
            elif any(term in company for term in ['university', 'college', 'institute']):
                cohort['company_type'] = 'academic'
            else:
                cohort['company_type'] = 'other'

        # Activity level
        contributions = prospect.get('contributions_last_year', 0)
        if contributions >= 100:
            cohort['activity_level'] = 'very_high'
        elif contributions >= 50:
            cohort['activity_level'] = 'high'
        elif contributions >= 10:
            cohort['activity_level'] = 'medium'
        else:
            cohort['activity_level'] = 'low'

        return cohort

