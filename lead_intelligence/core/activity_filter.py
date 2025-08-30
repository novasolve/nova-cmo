#!/usr/bin/env python3
"""
Activity Threshold Filter
Filters prospects based on recent activity and engagement levels
"""

import re
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

from .timezone_utils import parse_utc_datetime

logger = logging.getLogger(__name__)


@dataclass
class ActivityFilterResult:
    """Result of activity threshold filtering"""
    passes_filter: bool
    activity_score: float
    activity_reasons: List[str]
    activity_details: Dict[str, Any]


class ActivityThresholdFilter:
    """Filters prospects based on activity thresholds and engagement levels"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Default activity thresholds
        self.defaults = {
            'activity_days_threshold': config.get('activity_days_threshold', 90),
            'min_activity_score': config.get('min_activity_score', 0.6),
            'require_maintainer_status': config.get('require_maintainer_status', False),
            'require_recent_signal': config.get('require_recent_signal', True),
            'min_followers': config.get('min_followers', 5),
            'min_repos': config.get('min_repos', 3)
        }

        # Activity scoring weights
        self.weights = {
            'recency': 0.35,
            'signal_quality': 0.25,
            'engagement': 0.20,
            'maintainer_status': 0.15,
            'consistency': 0.05
        }

    def meets_activity_requirements(self, prospect: Dict[str, Any]) -> ActivityFilterResult:
        """
        Check if prospect meets activity threshold requirements
        Returns ActivityFilterResult with detailed scoring
        """
        activity_score = 0.0
        activity_reasons = []
        activity_details = {
            'recency_score': 0.0,
            'signal_quality_score': 0.0,
            'engagement_score': 0.0,
            'maintainer_score': 0.0,
            'consistency_score': 0.0,
            'days_since_last_activity': None,
            'signal_type': None,
            'has_maintainer_status': False
        }

        # 1. Check recency of activity
        recency_score, recency_reasons, days_since = self._check_activity_recency(prospect)
        activity_score += recency_score * self.weights['recency']
        activity_details['recency_score'] = recency_score
        activity_details['days_since_last_activity'] = days_since
        activity_reasons.extend(recency_reasons)

        # 2. Check signal quality
        signal_score, signal_reasons, signal_type = self._check_signal_quality(prospect)
        activity_score += signal_score * self.weights['signal_quality']
        activity_details['signal_quality_score'] = signal_score
        activity_details['signal_type'] = signal_type
        activity_reasons.extend(signal_reasons)

        # 3. Check engagement indicators
        engagement_score, engagement_reasons = self._check_engagement_indicators(prospect)
        activity_score += engagement_score * self.weights['engagement']
        activity_details['engagement_score'] = engagement_score
        activity_reasons.extend(engagement_reasons)

        # 4. Check maintainer status
        maintainer_score, maintainer_reasons, has_maintainer = self._check_maintainer_status(prospect)
        activity_score += maintainer_score * self.weights['maintainer_status']
        activity_details['maintainer_score'] = maintainer_score
        activity_details['has_maintainer_status'] = has_maintainer
        activity_reasons.extend(maintainer_reasons)

        # 5. Check activity consistency
        consistency_score, consistency_reasons = self._check_activity_consistency(prospect)
        activity_score += consistency_score * self.weights['consistency']
        activity_details['consistency_score'] = consistency_score
        activity_reasons.extend(consistency_reasons)

        # Determine if prospect passes filter
        min_score = self.defaults['min_activity_score']
        passes_filter = activity_score >= min_score

        # Add overall assessment
        if passes_filter:
            activity_reasons.insert(0, ".2f")
        else:
            activity_reasons.insert(0, ".2f")

        return ActivityFilterResult(
            passes_filter=passes_filter,
            activity_score=activity_score,
            activity_reasons=activity_reasons,
            activity_details=activity_details
        )

    def _check_activity_recency(self, prospect: Dict[str, Any]) -> Tuple[float, List[str], Optional[int]]:
        """Check how recent the prospect's activity is"""
        signal_at = prospect.get('signal_at')
        reasons = []
        days_since = None

        if not signal_at:
            return 0.0, ["No activity timestamp available"], None

        try:
            signal_date = parse_utc_datetime(signal_at)
            days_since = (datetime.now() - signal_date).days

            # Very recent (0-30 days)
            if days_since <= 30:
                score = 1.0
                reasons.append(f"Very recent activity ({days_since} days ago)")
            # Recent (31-60 days)
            elif days_since <= 60:
                score = 0.8
                reasons.append(f"Recent activity ({days_since} days ago)")
            # Moderately recent (61-90 days)
            elif days_since <= 90:
                score = 0.6
                reasons.append(f"Moderately recent activity ({days_since} days ago)")
            # Older (91-180 days)
            elif days_since <= 180:
                score = 0.3
                reasons.append(f"Some activity ({days_since} days ago)")
            # Very old (180+ days)
            else:
                score = 0.1
                reasons.append(f"Old activity ({days_since} days ago)")

            return score, reasons, days_since

        except Exception as e:
            self.logger.warning(f"Could not parse signal date '{signal_at}': {e}")
            return 0.0, ["Could not determine activity recency"], None

    def _check_signal_quality(self, prospect: Dict[str, Any]) -> Tuple[float, List[str], Optional[str]]:
        """Check the quality/type of activity signal"""
        signal_type = prospect.get('signal_type')
        signal = prospect.get('signal', '').strip()
        reasons = []

        if not signal_type:
            return 0.0, ["No signal type available"], None

        # Signal type hierarchy (PRs > Issues > Commits)
        signal_scores = {
            'pr': 1.0,      # Pull requests (highest quality)
            'issue': 0.7,   # Issues (good quality)
            'commit': 0.5   # Commits (moderate quality)
        }

        base_score = signal_scores.get(signal_type.lower(), 0.2)

        if signal_type.lower() == 'pr':
            reasons.append("Pull request activity (highest quality signal)")

            # Bonus for meaningful PR titles
            if signal and len(signal) > 20:
                base_score += 0.1
                reasons.append("Detailed PR title indicates quality contribution")

        elif signal_type.lower() == 'issue':
            reasons.append("Issue activity (good quality signal)")

            # Bonus for descriptive issues
            if signal and len(signal) > 30:
                base_score += 0.1
                reasons.append("Detailed issue description")

        elif signal_type.lower() == 'commit':
            reasons.append("Commit activity (moderate quality signal)")

            # Bonus for meaningful commit messages
            if signal and len(signal) > 15:
                base_score += 0.1
                reasons.append("Descriptive commit message")

        return min(base_score, 1.0), reasons, signal_type

    def _check_engagement_indicators(self, prospect: Dict[str, Any]) -> Tuple[float, List[str]]:
        """Check various engagement indicators"""
        reasons = []
        score = 0.0

        # Follower count
        followers = prospect.get('followers') or 0
        if followers >= 100:
            score += 0.3
            reasons.append(f"High follower count ({followers})")
        elif followers >= 50:
            score += 0.2
            reasons.append(f"Good follower count ({followers})")
        elif followers >= 10:
            score += 0.1
            reasons.append(f"Moderate follower count ({followers})")
        elif followers >= self.defaults['min_followers']:
            score += 0.05
            reasons.append(f"Basic follower count ({followers})")

        # Public repositories
        public_repos = prospect.get('public_repos') or 0
        if public_repos >= 50:
            score += 0.2
            reasons.append(f"High repository count ({public_repos})")
        elif public_repos >= 20:
            score += 0.15
            reasons.append(f"Good repository count ({public_repos})")
        elif public_repos >= 10:
            score += 0.1
            reasons.append(f"Moderate repository count ({public_repos})")
        elif public_repos >= self.defaults['min_repos']:
            score += 0.05
            reasons.append(f"Basic repository count ({public_repos})")

        # Following count (ratio check)
        following = prospect.get('following') or 0
        if followers > 0 and following > 0:
            ratio = following / followers
            if ratio <= 2.0:  # Not following too many people
                score += 0.1
                reasons.append(".1f")
            elif ratio <= 5.0:
                score += 0.05
                reasons.append(".1f")

        # Bio completeness
        bio = prospect.get('bio', '').strip()
        if bio:
            if len(bio) >= 100:
                score += 0.1
                reasons.append("Detailed bio (high engagement)")
            elif len(bio) >= 50:
                score += 0.05
                reasons.append("Good bio length (moderate engagement)")

        return min(score, 1.0), reasons

    def _check_maintainer_status(self, prospect: Dict[str, Any]) -> Tuple[float, List[str], bool]:
        """Check if prospect has maintainer/owner status"""
        reasons = []
        score = 0.0
        has_maintainer = False

        # Direct maintainer flags
        maintainer_indicators = [
            ('is_maintainer', prospect.get('is_maintainer')),
            ('is_codeowner', prospect.get('is_codeowner')),
            ('is_org_member', prospect.get('is_org_member'))
        ]

        for indicator_name, indicator_value in maintainer_indicators:
            if indicator_value:
                score += 0.4
                reasons.append(f"Direct {indicator_name} status")
                has_maintainer = True

        # Bio-based maintainer detection
        bio = prospect.get('bio', '').strip().lower()
        if bio:
            maintainer_keywords = [
                'maintainer', 'maintain', 'owner', 'creator', 'founder',
                'lead developer', 'core contributor', 'project lead'
            ]

            for keyword in maintainer_keywords:
                if keyword in bio:
                    score += 0.3
                    reasons.append(f"Bio indicates maintainer status ('{keyword}')")
                    has_maintainer = True
                    break

        # Repository name patterns (owner vs contributor)
        repo_full_name = prospect.get('repo_full_name', '')
        login = prospect.get('login', '')

        if repo_full_name and login:
            # If the login matches the repo owner, likely a maintainer
            repo_owner = repo_full_name.split('/')[0] if '/' in repo_full_name else ''
            if repo_owner and repo_owner.lower() == login.lower():
                score += 0.3
                reasons.append("Repository owner (maintainer status)")
                has_maintainer = True

        # If maintainer status is required but not found
        if self.defaults['require_maintainer_status'] and not has_maintainer:
            score = 0.0  # Force failure
            reasons.append("Maintainer status required but not detected")

        return min(score, 1.0), reasons, has_maintainer

    def _check_activity_consistency(self, prospect: Dict[str, Any]) -> Tuple[float, List[str]]:
        """Check consistency of activity patterns"""
        reasons = []
        score = 0.0

        # Check for multiple recent signals (consistency indicator)
        # This would require access to multiple signals per prospect
        # For now, we use available single-signal data

        signal_type = prospect.get('signal_type')
        if signal_type:
            score += 0.5
            reasons.append("Has activity signal (basic consistency)")

        # Check if profile appears complete
        required_fields = ['login', 'name', 'github_user_url']
        present_fields = sum(1 for field in required_fields if prospect.get(field))

        if present_fields == len(required_fields):
            score += 0.3
            reasons.append("Complete profile information")
        elif present_fields >= 2:
            score += 0.2
            reasons.append("Mostly complete profile")

        # Check for reasonable follower/following ratio
        followers = prospect.get('followers') or 0
        following = prospect.get('following') or 0

        if followers > 0 and following > 0:
            ratio = following / followers
            if 0.1 <= ratio <= 3.0:  # Reasonable ratio
                score += 0.2
                reasons.append(".1f")

        return min(score, 1.0), reasons

    def is_recently_active(self, prospect: Dict[str, Any]) -> bool:
        """Quick check if prospect is recently active (within threshold)"""
        signal_at = prospect.get('signal_at')
        if not signal_at:
            return False

        try:
            signal_date = parse_utc_datetime(signal_at)
            days_since = (datetime.now() - signal_date).days
            return days_since <= self.defaults['activity_days_threshold']
        except Exception:
            return False

    def filter_prospects(self, prospects: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Filter a list of prospects based on activity thresholds
        Returns: (passing_prospects, rejected_prospects)
        """
        passing = []
        rejected = []

        for prospect in prospects:
            filter_result = self.meets_activity_requirements(prospect)

            if filter_result.passes_filter:
                # Add activity metadata to prospect
                prospect_with_activity = prospect.copy()
                prospect_with_activity['activity_score'] = filter_result.activity_score
                prospect_with_activity['activity_reasons'] = filter_result.activity_reasons
                prospect_with_activity['activity_details'] = filter_result.activity_details
                passing.append(prospect_with_activity)
            else:
                rejected.append({
                    'prospect': prospect,
                    'rejection_reason': 'Activity threshold not met',
                    'activity_details': {
                        'activity_score': filter_result.activity_score,
                        'activity_reasons': filter_result.activity_reasons,
                        'details': filter_result.activity_details
                    }
                })

        self.logger.info(f"Activity filtering: {len(passing)} passing, {len(rejected)} rejected")
        return passing, rejected

    def get_activity_stats(self, prospects: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get statistics about activity levels for a set of prospects"""
        if not prospects:
            return {'total_prospects': 0}

        results = [self.meets_activity_requirements(prospect) for prospect in prospects]

        activity_scores = [r.activity_score for r in results]
        passing_count = sum(1 for r in results if r.passes_filter)

        # Activity recency distribution
        recency_distribution = {'0-30': 0, '31-60': 0, '61-90': 0, '91-180': 0, '180+': 0}
        for prospect in prospects:
            days = self._get_days_since_activity(prospect)
            if days is not None:
                if days <= 30:
                    recency_distribution['0-30'] += 1
                elif days <= 60:
                    recency_distribution['31-60'] += 1
                elif days <= 90:
                    recency_distribution['61-90'] += 1
                elif days <= 180:
                    recency_distribution['91-180'] += 1
                else:
                    recency_distribution['180+'] += 1

        return {
            'total_prospects': len(prospects),
            'passing_prospects': passing_count,
            'pass_rate': passing_count / len(prospects),
            'avg_activity_score': sum(activity_scores) / len(activity_scores),
            'min_activity_score': min(activity_scores),
            'max_activity_score': max(activity_scores),
            'threshold': self.defaults['min_activity_score'],
            'recency_distribution': recency_distribution
        }

    def _get_days_since_activity(self, prospect: Dict[str, Any]) -> Optional[int]:
        """Get days since last activity for a prospect"""
        signal_at = prospect.get('signal_at')
        if not signal_at:
            return None

        try:
            signal_date = parse_utc_datetime(signal_at)
            return (datetime.now() - signal_date).days
        except Exception:
            return None
