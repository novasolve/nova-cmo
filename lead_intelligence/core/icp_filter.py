#!/usr/bin/env python3
"""
ICP Relevance Filter
Filters prospects based on Ideal Customer Profile matching
"""

import re
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging

from .timezone_utils import parse_utc_datetime

logger = logging.getLogger(__name__)


@dataclass
class ICPMatchResult:
    """Result of ICP relevance filtering"""
    is_relevant: bool
    relevance_score: float
    match_reasons: List[str]
    match_details: Dict[str, Any]


class ICPRelevanceFilter:
    """Filters prospects based on ICP (Ideal Customer Profile) matching"""

    def __init__(self, icp_config: Dict[str, Any]):
        self.icp_config = icp_config
        self.logger = logging.getLogger(__name__)

        # ICP criteria weights
        self.weights = {
            'company_size': 0.25,
            'tech_stack': 0.30,
            'activity_level': 0.20,
            'location': 0.15,
            'engagement': 0.10
        }

        # Company size ranges (revenue or employee count)
        self.company_size_ranges = {
            'seed': {
                'min_employees': 1,
                'max_employees': 50,
                'revenue_range': '0-5M',
                'indicators': ['seed', 'pre-seed', 'bootstrap', 'startup', 'early stage']
            },
            'series_a': {
                'min_employees': 10,
                'max_employees': 100,
                'revenue_range': '2-20M',
                'indicators': ['series a', 'series-a', 'a round', 'growth stage']
            },
            'series_b_plus': {
                'min_employees': 50,
                'max_employees': 1000,
                'revenue_range': '10M+',
                'indicators': ['series b', 'series-b', 'series c', 'series-c', 'growth', 'scale']
            }
        }

        # Technology stack keywords
        self.tech_stacks = {
            'python_ml': {
                'languages': ['python', 'py'],
                'frameworks': ['tensorflow', 'pytorch', 'scikit-learn', 'pandas', 'numpy', 'jupyter'],
                'keywords': ['machine learning', 'ml', 'ai', 'artificial intelligence', 'data science', 'deep learning']
            },
            'web_dev': {
                'languages': ['javascript', 'typescript', 'js', 'ts'],
                'frameworks': ['react', 'vue', 'angular', 'next.js', 'nuxt', 'svelte'],
                'keywords': ['frontend', 'backend', 'full-stack', 'web development']
            },
            'devops': {
                'languages': ['go', 'rust', 'python'],
                'frameworks': ['kubernetes', 'docker', 'terraform', 'ansible'],
                'keywords': ['devops', 'infrastructure', 'ci/cd', 'cloud', 'aws', 'gcp', 'azure']
            },
            'api_sdk': {
                'languages': ['python', 'go', 'rust', 'typescript'],
                'frameworks': ['fastapi', 'flask', 'django', 'express', 'graphql'],
                'keywords': ['api', 'sdk', 'client', 'library', 'framework', 'platform']
            },
            'data_science': {
                'languages': ['python', 'r', 'julia'],
                'frameworks': ['pandas', 'numpy', 'scipy', 'matplotlib', 'seaborn'],
                'keywords': ['data science', 'analytics', 'visualization', 'statistics', 'ml']
            }
        }

    def is_relevant(self, prospect: Dict[str, Any]) -> ICPMatchResult:
        """
        Determine if a prospect matches the ICP criteria
        Returns ICPMatchResult with relevance score and match reasons
        """
        relevance_score = 0.0
        match_reasons = []
        match_details = {
            'company_size_match': 0.0,
            'tech_stack_match': 0.0,
            'activity_match': 0.0,
            'location_match': 0.0,
            'engagement_match': 0.0
        }

        # 1. Company size matching
        company_size_score, company_reasons = self._match_company_size(prospect)
        relevance_score += company_size_score * self.weights['company_size']
        match_details['company_size_match'] = company_size_score
        if company_reasons:
            match_reasons.extend(company_reasons)

        # 2. Technology stack matching
        tech_stack_score, tech_reasons = self._match_tech_stack(prospect)
        relevance_score += tech_stack_score * self.weights['tech_stack']
        match_details['tech_stack_match'] = tech_stack_score
        if tech_reasons:
            match_reasons.extend(tech_reasons)

        # 3. Activity level matching
        activity_score, activity_reasons = self._match_activity_level(prospect)
        relevance_score += activity_score * self.weights['activity_level']
        match_details['activity_match'] = activity_score
        if activity_reasons:
            match_reasons.extend(activity_reasons)

        # 4. Location preferences
        location_score, location_reasons = self._match_location_preferences(prospect)
        relevance_score += location_score * self.weights['location']
        match_details['location_match'] = location_score
        if location_reasons:
            match_reasons.extend(location_reasons)

        # 5. Engagement indicators
        engagement_score, engagement_reasons = self._match_engagement_indicators(prospect)
        relevance_score += engagement_score * self.weights['engagement']
        match_details['engagement_match'] = engagement_score
        if engagement_reasons:
            match_reasons.extend(engagement_reasons)

        # Determine if relevant based on threshold
        relevance_threshold = self.icp_config.get('relevance_threshold', 0.6)
        is_relevant = relevance_score >= relevance_threshold

        # Add overall assessment
        if is_relevant:
            match_reasons.insert(0, ".2f")
        else:
            match_reasons.insert(0, ".2f")

        return ICPMatchResult(
            is_relevant=is_relevant,
            relevance_score=relevance_score,
            match_reasons=match_reasons,
            match_details=match_details
        )

    def _match_company_size(self, prospect: Dict[str, Any]) -> Tuple[float, List[str]]:
        """Match prospect against company size criteria"""
        company = prospect.get('company', '').strip().lower()
        bio = prospect.get('bio', '').strip().lower()
        location = prospect.get('location', '').strip().lower()

        if not company and not bio:
            return 0.0, ["No company information available"]

        reasons = []
        max_score = 0.0

        # Check company name for size indicators
        for size_category, criteria in self.company_size_ranges.items():
            score = 0.0
            category_reasons = []

            # Check for explicit size indicators in company name
            for indicator in criteria['indicators']:
                if indicator in company:
                    score += 0.8
                    category_reasons.append(f"Company name indicates {size_category} stage")

            # Check bio for size indicators
            if bio:
                for indicator in criteria['indicators']:
                    if indicator in bio:
                        score += 0.6
                        category_reasons.append(f"Bio indicates {size_category} stage")

            # Location-based size hints (tech hubs suggest growth stage)
            tech_hubs = ['san francisco', 'palo alto', 'mountain view', 'seattle', 'austin', 'boston']
            if any(hub in location for hub in tech_hubs):
                if size_category in ['series_a', 'series_b_plus']:
                    score += 0.3
                    category_reasons.append("Location suggests growth-stage company")

            # Check ICP preferences for company size
            icp_company_sizes = self.icp_config.get('company_sizes', [])
            if size_category in icp_company_sizes:
                score += 0.4
                category_reasons.append(f"Matches ICP target: {size_category}")

            if score > max_score:
                max_score = score
                reasons = category_reasons

        # If no specific indicators found, assume neutral score for small companies
        if max_score == 0.0 and company:
            return 0.5, ["Company size unclear, assuming small/medium"]

        return min(max_score, 1.0), reasons

    def _match_tech_stack(self, prospect: Dict[str, Any]) -> Tuple[float, List[str]]:
        """Match prospect against technology stack criteria"""
        bio = prospect.get('bio', '').strip().lower()
        topics = [topic.lower() for topic in prospect.get('topics', [])]
        language = prospect.get('language', '').strip().lower()
        repo_name = prospect.get('repo_full_name', '').strip().lower()

        if not any([bio, topics, language, repo_name]):
            return 0.0, ["No technology information available"]

        reasons = []
        total_score = 0.0
        match_count = 0

        # Get target tech stacks from ICP config
        target_stacks = self.icp_config.get('tech_stacks', [])

        for stack_name in target_stacks:
            if stack_name not in self.tech_stacks:
                continue

            stack_config = self.tech_stacks[stack_name]
            stack_score = 0.0
            stack_reasons = []

            # Check programming language
            if language and language in stack_config['languages']:
                stack_score += 0.4
                stack_reasons.append(f"Primary language {language} matches {stack_name}")

            # Check repository topics
            for topic in topics:
                for keyword in stack_config['keywords']:
                    if keyword in topic:
                        stack_score += 0.3
                        stack_reasons.append(f"Topic '{topic}' matches {stack_name}")
                        break

            # Check bio for tech keywords
            if bio:
                for keyword in stack_config['keywords']:
                    if keyword in bio:
                        stack_score += 0.2
                        stack_reasons.append(f"Bio mentions {keyword} ({stack_name})")

                # Check for framework mentions in bio
                for framework in stack_config['frameworks']:
                    if framework in bio:
                        stack_score += 0.3
                        stack_reasons.append(f"Bio mentions {framework} ({stack_name})")

            # Check repository name for tech indicators
            if repo_name:
                for keyword in stack_config['keywords']:
                    if keyword in repo_name:
                        stack_score += 0.2
                        stack_reasons.append(f"Repo name suggests {stack_name}")

            # If this stack has any matches, count it
            if stack_score > 0:
                total_score += min(stack_score, 1.0)
                match_count += 1
                reasons.extend(stack_reasons)

        # Average score across matched stacks
        if match_count > 0:
            final_score = total_score / match_count
            return min(final_score, 1.0), reasons
        else:
            return 0.0, ["No matching technology stack found"]

    def _match_activity_level(self, prospect: Dict[str, Any]) -> Tuple[float, List[str]]:
        """Match prospect against activity level criteria"""
        signal_at = prospect.get('signal_at')
        signal_type = prospect.get('signal_type')
        followers = prospect.get('followers') or 0
        public_repos = prospect.get('public_repos') or 0

        reasons = []
        score = 0.0

        # Check recency of activity
        if signal_at:
            try:
                signal_date = parse_utc_datetime(signal_at)
                days_since = (datetime.now() - signal_date).days

                # Very recent activity (last 30 days)
                if days_since <= 30:
                    score += 0.5
                    reasons.append(f"Very recent activity ({days_since} days ago)")
                # Recent activity (last 90 days)
                elif days_since <= 90:
                    score += 0.3
                    reasons.append(f"Recent activity ({days_since} days ago)")
                # Older activity
                elif days_since <= 180:
                    score += 0.1
                    reasons.append(f"Some recent activity ({days_since} days ago)")
                else:
                    reasons.append(f"Older activity ({days_since} days ago)")

            except Exception as e:
                self.logger.warning(f"Could not parse signal date: {e}")
                reasons.append("Could not determine activity recency")
        else:
            reasons.append("No activity timestamp available")

        # Check signal type (PRs are better than issues/commits)
        if signal_type:
            if signal_type == 'pr':
                score += 0.2
                reasons.append("Pull request activity (high engagement)")
            elif signal_type == 'issue':
                score += 0.1
                reasons.append("Issue activity (moderate engagement)")
            elif signal_type == 'commit':
                score += 0.1
                reasons.append("Commit activity (moderate engagement)")

        # Check follower count as engagement indicator
        if followers > 0:
            if followers >= 100:
                score += 0.2
                reasons.append(f"High follower count ({followers})")
            elif followers >= 50:
                score += 0.1
                reasons.append(f"Good follower count ({followers})")
            elif followers >= 10:
                score += 0.05
                reasons.append(f"Moderate follower count ({followers})")

        # Check repository count
        if public_repos > 0:
            if public_repos >= 50:
                score += 0.1
                reasons.append(f"High repository count ({public_repos})")
            elif public_repos >= 20:
                score += 0.05
                reasons.append(f"Good repository count ({public_repos})")

        # Check for maintainer status
        maintainer_indicators = [
            prospect.get('is_maintainer'),
            prospect.get('is_codeowner'),
            prospect.get('is_org_member'),
            'maintainer' in prospect.get('bio', '').lower()
        ]

        if any(maintainer_indicators):
            score += 0.3
            reasons.append("Maintainer or owner status detected")

        return min(score, 1.0), reasons

    def _match_location_preferences(self, prospect: Dict[str, Any]) -> Tuple[float, List[str]]:
        """Match prospect against location preferences"""
        location = prospect.get('location', '').strip().lower()
        company = prospect.get('company', '').strip().lower()

        if not location:
            return 0.5, ["No location information available"]

        reasons = []
        score = 0.0

        # Get preferred locations from ICP config
        preferred_locations = self.icp_config.get('preferred_locations', [])
        blocked_locations = self.icp_config.get('blocked_locations', [])

        # Check for blocked locations first
        for blocked in blocked_locations:
            if blocked.lower() in location:
                return 0.0, [f"Location blocked: {blocked}"]

        # Check for preferred locations
        for preferred in preferred_locations:
            if preferred.lower() in location:
                score += 0.8
                reasons.append(f"Preferred location: {preferred}")
                break

        # US-based preferences
        us_cities = ['san francisco', 'palo alto', 'mountain view', 'seattle', 'austin', 'boston', 'new york', 'san jose']
        if any(city in location for city in us_cities):
            if 'us' in preferred_locations or 'united states' in preferred_locations:
                score += 0.6
                reasons.append("US tech hub location")

        # English-speaking countries
        english_countries = ['united states', 'canada', 'united kingdom', 'australia', 'new zealand']
        if any(country in location for country in english_countries):
            score += 0.3
            reasons.append("English-speaking country")

        # If no specific preferences matched but location exists
        if score == 0.0 and location:
            score = 0.4  # Neutral score for unknown but present location
            reasons.append("Location provided but not in ICP preferences")

        return min(score, 1.0), reasons

    def _match_engagement_indicators(self, prospect: Dict[str, Any]) -> Tuple[float, List[str]]:
        """Match prospect against engagement indicators"""
        reasons = []
        score = 0.0

        # Check for LinkedIn presence
        if prospect.get('linkedin_username'):
            score += 0.4
            reasons.append("LinkedIn profile available")

        # Check for blog/website
        if prospect.get('blog'):
            score += 0.3
            reasons.append("Personal blog/website available")

        # Check for comprehensive bio
        bio = prospect.get('bio', '').strip()
        if bio and len(bio) > 50:
            score += 0.2
            reasons.append("Detailed bio available")

        # Check for company information
        if prospect.get('company'):
            score += 0.1
            reasons.append("Company information available")

        return min(score, 1.0), reasons

    def filter_prospects(self, prospects: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Filter a list of prospects based on ICP relevance
        Returns: (relevant_prospects, rejected_prospects)
        """
        relevant = []
        rejected = []

        for prospect in prospects:
            match_result = self.is_relevant(prospect)

            if match_result.is_relevant:
                # Add ICP matching metadata to prospect
                prospect_with_icp = prospect.copy()
                prospect_with_icp['icp_relevance_score'] = match_result.relevance_score
                prospect_with_icp['icp_match_reasons'] = match_result.match_reasons
                prospect_with_icp['icp_match_details'] = match_result.match_details
                relevant.append(prospect_with_icp)
            else:
                rejected.append({
                    'prospect': prospect,
                    'rejection_reason': 'ICP mismatch',
                    'icp_details': {
                        'relevance_score': match_result.relevance_score,
                        'match_reasons': match_result.match_reasons,
                        'match_details': match_result.match_details
                    }
                })

        self.logger.info(f"ICP filtering: {len(relevant)} relevant, {len(rejected)} rejected")
        return relevant, rejected

    def get_icp_stats(self, prospects: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Get statistics about ICP matching for a set of prospects"""
        if not prospects:
            return {'total_prospects': 0}

        results = [self.is_relevant(prospect) for prospect in prospects]

        relevance_scores = [r.relevance_score for r in results]
        relevant_count = sum(1 for r in results if r.is_relevant)

        return {
            'total_prospects': len(prospects),
            'relevant_prospects': relevant_count,
            'relevance_rate': relevant_count / len(prospects),
            'avg_relevance_score': sum(relevance_scores) / len(relevance_scores),
            'min_relevance_score': min(relevance_scores),
            'max_relevance_score': max(relevance_scores),
            'threshold': self.icp_config.get('relevance_threshold', 0.6)
        }
