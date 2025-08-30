#!/usr/bin/env python3
"""
Lead Intelligence Analyzer
Advanced analysis module for processing and scoring leads
"""

import re
import json
from typing import Dict, List, Any, Optional, Set
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


@dataclass
class LeadScore:
    """Structured lead scoring result"""
    total_score: float
    component_scores: Dict[str, float]
    quality_signals: List[str]
    risk_signals: List[str]
    opportunity_signals: List[str]
    confidence_level: str
    analysis_metadata: Dict[str, Any]


class LeadAnalyzer:
    """Advanced lead analysis and scoring engine"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        self.logger = logger

    def _default_config(self) -> Dict[str, Any]:
        """Default configuration for analysis"""
        return {
            'scoring_weights': {
                'email_quality': 3.0,
                'profile_completeness': 2.0,
                'social_presence': 2.0,
                'activity_level': 1.5,
                'network_influence': 1.0,
                'technical_expertise': 1.5,
                'professional_signals': 1.0
            },
            'quality_thresholds': {
                'high': 5.0,
                'medium': 3.0,
                'low': 1.0
            },
            'public_domains': {
                'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
                'aol.com', 'proton.me', 'protonmail.com', 'icloud.com'
            },
            'modern_tech': {
                'python', 'javascript', 'typescript', 'go', 'rust',
                'kotlin', 'swift', 'dart', 'elixir', 'clojure'
            }
        }

    def analyze_lead(self, lead_data: Dict[str, Any]) -> LeadScore:
        """Perform comprehensive analysis of a lead"""
        try:
            component_scores = {}

            # Email quality analysis
            component_scores['email_quality'] = self._analyze_email_quality(lead_data)

            # Profile completeness
            component_scores['profile_completeness'] = self._analyze_profile_completeness(lead_data)

            # Social presence
            component_scores['social_presence'] = self._analyze_social_presence(lead_data)

            # Activity level
            component_scores['activity_level'] = self._analyze_activity_level(lead_data)

            # Network influence
            component_scores['network_influence'] = self._analyze_network_influence(lead_data)

            # Technical expertise
            component_scores['technical_expertise'] = self._analyze_technical_expertise(lead_data)

            # Professional signals
            component_scores['professional_signals'] = self._analyze_professional_signals(lead_data)

            # Calculate total score
            total_score = sum(
                score * self.config['scoring_weights'].get(component, 1.0)
                for component, score in component_scores.items()
            )

            # Identify signals
            quality_signals = self._identify_quality_signals(lead_data, component_scores)
            risk_signals = self._identify_risk_signals(lead_data, component_scores)
            opportunity_signals = self._identify_opportunity_signals(lead_data, component_scores)

            # Determine confidence level
            confidence_level = self._calculate_confidence_level(component_scores)

            return LeadScore(
                total_score=round(total_score, 2),
                component_scores=component_scores,
                quality_signals=quality_signals,
                risk_signals=risk_signals,
                opportunity_signals=opportunity_signals,
                confidence_level=confidence_level,
                analysis_metadata={
                    'analyzed_at': datetime.now().isoformat(),
                    'analysis_version': '1.0',
                    'components_analyzed': len(component_scores)
                }
            )

        except Exception as e:
            self.logger.error(f"Error analyzing lead {lead_data.get('login', 'unknown')}: {e}")
            return self._empty_score()

    def _analyze_email_quality(self, lead: Dict[str, Any]) -> float:
        """Analyze email quality and reliability"""
        score = 0.0

        email_profile = lead.get('email_profile')
        email_commit = lead.get('email_public_commit')

        # Profile email is most valuable
        if email_profile:
            score += 2.0
            # Check if it's a corporate domain
            if '@' in email_profile:
                domain = email_profile.split('@')[1].lower()
                if domain not in self.config['public_domains']:
                    score += 1.0  # Corporate email bonus

        # Commit email is less reliable but still valuable
        if email_commit and not email_profile:
            score += 1.0
            if '@' in email_commit:
                domain = email_commit.split('@')[1].lower()
                if domain not in self.config['public_domains']:
                    score += 0.5

        return min(score, 3.0)

    def _analyze_profile_completeness(self, lead: Dict[str, Any]) -> float:
        """Analyze how complete the profile information is"""
        score = 0.0
        max_score = 5.0

        # Required fields
        if lead.get('name'):
            score += 1.0
        if lead.get('company'):
            score += 1.0
        if lead.get('location'):
            score += 1.0
        if lead.get('bio'):
            score += 1.0
        if lead.get('pronouns'):
            score += 0.5

        # Bonus for detailed bio
        if lead.get('bio') and len(str(lead['bio'])) > 100:
            score += 0.5

        return min(score, max_score)

    def _analyze_social_presence(self, lead: Dict[str, Any]) -> float:
        """Analyze social media and professional presence"""
        score = 0.0

        # GitHub social features
        if lead.get('twitter_username'):
            score += 0.5
        if lead.get('blog'):
            score += 0.5
        if lead.get('linkedin_username') or 'linkedin.com' in str(lead.get('blog', '')):
            score += 1.0

        # Professional indicators
        if lead.get('hireable'):
            score += 0.5

        return min(score, 2.0)

    def _analyze_activity_level(self, lead: Dict[str, Any]) -> float:
        """Analyze GitHub activity level"""
        score = 0.0

        # Repository activity
        public_repos = lead.get('public_repos') or 0
        if public_repos > 50:
            score += 1.0
        elif public_repos > 20:
            score += 0.7
        elif public_repos > 5:
            score += 0.4

        # Contribution activity
        contributions = lead.get('contributions_last_year') or 0
        if contributions > 100:
            score += 1.0
        elif contributions > 50:
            score += 0.7
        elif contributions > 10:
            score += 0.4

        return min(score, 2.0)

    def _analyze_network_influence(self, lead: Dict[str, Any]) -> float:
        """Analyze network influence and reach"""
        score = 0.0

        # Follower analysis
        followers = lead.get('followers') or 0
        if followers > 1000:
            score += 1.0
        elif followers > 100:
            score += 0.7
        elif followers > 50:
            score += 0.4

        # Following analysis (influencers follow fewer people)
        following = lead.get('following') or 0
        if followers > following * 2:
            score += 0.3  # Influencer pattern

        return min(score, 1.0)

    def _analyze_technical_expertise(self, lead: Dict[str, Any]) -> float:
        """Analyze technical expertise and skills"""
        score = 0.0

        # Primary language analysis
        language = str(lead.get('language', '')).lower()
        if language in self.config['modern_tech']:
            score += 0.8

        # Stars on repositories (maintainer quality)
        stars = lead.get('stars') or 0
        if stars > 1000:
            score += 0.7
        elif stars > 100:
            score += 0.4

        return min(score, 1.5)

    def _analyze_professional_signals(self, lead: Dict[str, Any]) -> float:
        """Analyze professional and career signals"""
        score = 0.0

        # Company analysis
        company = str(lead.get('company', '')).strip()
        if company and len(company) > 2 and not company.lower().startswith('@'):
            score += 0.5

        # Location analysis (professional hubs)
        location = str(lead.get('location', '')).lower()
        professional_hubs = ['san francisco', 'new york', 'london', 'berlin', 'singapore']
        if any(hub in location for hub in professional_hubs):
            score += 0.3

        # Account age (experienced developers)
        created_at = lead.get('created_at')
        if created_at:
            try:
                created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                years_active = (datetime.now() - created_date).days / 365
                if years_active > 5:
                    score += 0.5
                elif years_active > 2:
                    score += 0.3
            except:
                pass

        return min(score, 1.0)

    def _identify_quality_signals(self, lead: Dict[str, Any], scores: Dict[str, float]) -> List[str]:
        """Identify positive quality signals"""
        signals = []

        if scores.get('email_quality', 0) >= 2.0:
            signals.append('strong_email_signal')
        if scores.get('profile_completeness', 0) >= 4.0:
            signals.append('complete_profile')
        if scores.get('social_presence', 0) >= 1.5:
            signals.append('strong_social_presence')
        if scores.get('activity_level', 0) >= 1.5:
            signals.append('highly_active')
        if scores.get('network_influence', 0) >= 0.7:
            signals.append('influential_network')
        if scores.get('technical_expertise', 0) >= 1.2:
            signals.append('technical_expertise')

        return signals

    def _identify_risk_signals(self, lead: Dict[str, Any], scores: Dict[str, float]) -> List[str]:
        """Identify potential risk signals"""
        risks = []

        if scores.get('email_quality', 0) < 1.0:
            risks.append('weak_email_signal')
        if scores.get('profile_completeness', 0) < 2.0:
            risks.append('incomplete_profile')
        if scores.get('activity_level', 0) < 0.5:
            risks.append('low_activity')
        if not lead.get('company'):
            risks.append('no_company_info')

        return risks

    def _identify_opportunity_signals(self, lead: Dict[str, Any], scores: Dict[str, float]) -> List[str]:
        """Identify opportunity signals"""
        opportunities = []

        if scores.get('network_influence', 0) >= 0.7:
            opportunities.append('networking_potential')
        if scores.get('technical_expertise', 0) >= 1.0:
            opportunities.append('technical_collaboration')
        if lead.get('hireable'):
            opportunities.append('hiring_opportunity')
        if scores.get('activity_level', 0) >= 1.0:
            opportunities.append('engagement_potential')

        return opportunities

    def _calculate_confidence_level(self, scores: Dict[str, float]) -> str:
        """Calculate confidence level in the analysis"""
        # High confidence if we have good data across multiple components
        high_score_components = sum(1 for score in scores.values() if score >= 1.0)

        if high_score_components >= 5:
            return 'high'
        elif high_score_components >= 3:
            return 'medium'
        else:
            return 'low'

    def _empty_score(self) -> LeadScore:
        """Return empty score for error cases"""
        return LeadScore(
            total_score=0.0,
            component_scores={},
            quality_signals=[],
            risk_signals=['analysis_error'],
            opportunity_signals=[],
            confidence_level='low',
            analysis_metadata={'error': True}
        )

    def batch_analyze(self, leads: List[Dict[str, Any]]) -> List[LeadScore]:
        """Analyze multiple leads efficiently"""
        results = []
        for lead in leads:
            score = self.analyze_lead(lead)
            results.append(score)
        return results


class LeadClusterAnalyzer:
    """Analyze clusters and patterns in leads"""

    def __init__(self):
        self.logger = logger

    def analyze_company_clusters(self, leads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze company concentration and clusters"""
        companies = Counter()

        for lead in leads:
            company = str(lead.get('company', '')).strip()
            if company and len(company) > 2:
                # Normalize company names
                company = company.lower().replace('@', '').strip()
                companies[company] += 1

        # Find significant clusters
        clusters = {
            company: count
            for company, count in companies.items()
            if count >= 2  # At least 2 people from same company
        }

        return {
            'total_companies': len(companies),
            'clustered_companies': len(clusters),
            'top_companies': dict(companies.most_common(10)),
            'company_clusters': dict(sorted(clusters.items(), key=lambda x: x[1], reverse=True))
        }

    def analyze_technology_clusters(self, leads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze technology and language clusters"""
        technologies = Counter()

        for lead in leads:
            tech = str(lead.get('language', '')).lower().strip()
            if tech:
                technologies[tech] += 1

        return {
            'total_technologies': len(technologies),
            'top_technologies': dict(technologies.most_common(10)),
            'technology_distribution': dict(technologies)
        }

    def analyze_geographic_clusters(self, leads: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze geographic concentration"""
        locations = Counter()

        for lead in leads:
            location = str(lead.get('location', '')).strip()
            if location:
                # Simple location normalization
                location = location.lower()
                locations[location] += 1

        return {
            'total_locations': len(locations),
            'top_locations': dict(locations.most_common(10)),
            'location_distribution': dict(locations)
        }

    def find_network_opportunities(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find networking and collaboration opportunities"""
        opportunities = []

        # Company-based opportunities
        company_clusters = self.analyze_company_clusters(leads)
        for company, count in company_clusters['company_clusters'].items():
            if count >= 3:
                opportunities.append({
                    'type': 'company_cluster',
                    'company': company,
                    'size': count,
                    'potential': 'team_expansion'
                })

        # Technology-based opportunities
        tech_clusters = self.analyze_technology_clusters(leads)
        for tech, count in tech_clusters['technology_distribution'].items():
            if count >= 5:
                opportunities.append({
                    'type': 'technology_cluster',
                    'technology': tech,
                    'size': count,
                    'potential': 'community_building'
                })

        return opportunities
