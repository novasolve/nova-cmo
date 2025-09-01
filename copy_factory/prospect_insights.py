#!/usr/bin/env python3
"""
AI-Powered Prospect Insights and Recommendations System
Provides deep insights into prospects and actionable recommendations
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from collections import defaultdict

from .content_analyzer import ContentAnalyzer
from .smart_icp_matcher import SmartICPMatcher
from .ai_copy_generator import AICopyGenerator
from .core.storage import CopyFactoryStorage

logger = logging.getLogger(__name__)


class ProspectInsightsEngine:
    """AI-powered prospect insights and recommendations"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.content_analyzer = ContentAnalyzer(api_key)
        self.icp_matcher = SmartICPMatcher(api_key)
        self.ai_generator = AICopyGenerator(api_key)
        self.storage = CopyFactoryStorage()

        # Insights cache
        self.insights_dir = "copy_factory/data/insights"
        os.makedirs(self.insights_dir, exist_ok=True)

    def generate_comprehensive_insights(self, prospect: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive insights for a prospect"""

        prospect_id = prospect.get('lead_id') or prospect.get('login')

        # Check cache first
        cached = self._get_cached_insights(prospect_id)
        if cached:
            return cached

        # Generate fresh insights
        insights = {
            'prospect_id': prospect_id,
            'generated_at': datetime.now().isoformat(),
            'profile_analysis': {},
            'behavioral_insights': {},
            'engagement_prediction': {},
            'outreach_recommendations': {},
            'risk_assessment': {},
            'opportunity_score': 0
        }

        try:
            # Convert dict to prospect object if needed
            if isinstance(prospect, dict):
                from .core.models import ProspectData
                prospect_obj = ProspectData(**prospect)
            else:
                prospect_obj = prospect

            # Profile analysis
            insights['profile_analysis'] = self._analyze_prospect_profile(prospect_obj)

            # Behavioral insights
            insights['behavioral_insights'] = self._analyze_behavioral_patterns(prospect_obj)

            # Engagement prediction
            insights['engagement_prediction'] = self._predict_engagement_potential(prospect_obj)

            # Outreach recommendations
            insights['outreach_recommendations'] = self._generate_outreach_strategy(prospect_obj)

            # Risk assessment
            insights['risk_assessment'] = self._assess_outreach_risks(prospect_obj)

            # Overall opportunity score
            insights['opportunity_score'] = self._calculate_opportunity_score(insights)

        except Exception as e:
            logger.error(f"Error generating insights for prospect {prospect_id}: {e}")
            insights['error'] = str(e)

        # Cache the insights
        self._cache_insights(prospect_id, insights)

        return insights

    def _analyze_prospect_profile(self, prospect: 'ProspectData') -> Dict[str, Any]:
        """Analyze prospect's profile comprehensively"""

        analysis = {
            'professional_level': 'unknown',
            'technical_expertise': {},
            'interests_alignment': [],
            'content_quality': 'medium',
            'network_influence': 'low',
            'engagement_readiness': 'medium'
        }

        # Professional level assessment
        activity_score = 0
        if prospect.contributions_last_year:
            activity_score += min(prospect.contributions_last_year / 50, 2)
        if prospect.followers:
            activity_score += min(prospect.followers / 100, 2)
        if prospect.public_repos:
            activity_score += min(prospect.public_repos / 20, 2)

        if activity_score >= 4:
            analysis['professional_level'] = 'expert'
        elif activity_score >= 2:
            analysis['professional_level'] = 'advanced'
        else:
            analysis['professional_level'] = 'developing'

        # Technical expertise
        analysis['technical_expertise'] = self.content_analyzer._extract_technical_expertise(prospect)

        # Network influence
        if prospect.followers is not None and prospect.followers > 500:
            analysis['network_influence'] = 'high'
        elif prospect.followers is not None and prospect.followers > 100:
            analysis['network_influence'] = 'medium'

        return analysis

    def _analyze_behavioral_patterns(self, prospect: 'ProspectData') -> Dict[str, Any]:
        """Analyze prospect's behavioral patterns"""

        patterns = {
            'activity_consistency': 'unknown',
            'collaboration_style': 'individual',
            'content_creation': 'low',
            'community_engagement': 'low',
            'technical_focus': []
        }

        # Activity consistency
        if prospect.contributions_last_year and prospect.contributions_last_year > 12:
            patterns['activity_consistency'] = 'high'
        elif prospect.contributions_last_year and prospect.contributions_last_year > 6:
            patterns['activity_consistency'] = 'medium'
        else:
            patterns['activity_consistency'] = 'low'

        # Collaboration style
        if prospect.forks and prospect.forks > prospect.public_repos:
            patterns['collaboration_style'] = 'collaborative'

        # Content creation
        if prospect.public_repos and prospect.public_repos > 15:
            patterns['content_creation'] = 'high'
        elif prospect.public_repos and prospect.public_repos > 5:
            patterns['content_creation'] = 'medium'

        # Technical focus from topics
        if prospect.topics:
            tech_focus = []
            for topic in prospect.topics[:5]:  # Top 5 topics
                if any(keyword in topic.lower() for keyword in ['ai', 'ml', 'data', 'web', 'api', 'cloud']):
                    tech_focus.append(topic)
            patterns['technical_focus'] = tech_focus

        return patterns

    def _predict_engagement_potential(self, prospect: 'ProspectData') -> Dict[str, Any]:
        """Predict prospect's engagement potential"""

        prediction = {
            'overall_potential': 'medium',
            'response_likelihood': 0.5,
            'conversion_probability': 0.1,
            'best_contact_method': 'email',
            'optimal_timing': 'business_hours',
            'engagement_drivers': []
        }

        # Calculate response likelihood
        base_score = 0.3  # Base likelihood

        # Email quality boost
        if prospect.has_email():
            base_score += 0.3
            if '@' in (prospect.get_best_email() or '') and 'gmail.com' not in prospect.get_best_email():
                base_score += 0.1  # Corporate email bonus

        # Activity boost
        if prospect.contributions_last_year and prospect.contributions_last_year > 20:
            base_score += 0.2

        # Network boost
        if prospect.followers is not None and prospect.followers > 50:
            base_score += 0.1

        prediction['response_likelihood'] = min(base_score, 0.9)

        # Determine overall potential
        if prediction['response_likelihood'] > 0.7:
            prediction['overall_potential'] = 'high'
        elif prediction['response_likelihood'] > 0.4:
            prediction['overall_potential'] = 'medium'
        else:
            prediction['overall_potential'] = 'low'

        # Engagement drivers
        if prospect.has_email():
            prediction['engagement_drivers'].append('direct_contact_available')
        if prospect.contributions_last_year and prospect.contributions_last_year > 10:
            prediction['engagement_drivers'].append('active_contributor')
        if prospect.bio and len(prospect.bio) > 50:
            prediction['engagement_drivers'].append('detailed_profile')

        return prediction

    def _generate_outreach_strategy(self, prospect: 'ProspectData') -> Dict[str, Any]:
        """Generate personalized outreach strategy"""

        strategy = {
            'primary_approach': 'direct_email',
            'tone_recommendation': 'professional',
            'value_proposition_focus': 'technical_solution',
            'timing_strategy': 'business_hours_weekdays',
            'follow_up_sequence': [],
            'channel_mix': ['email'],
            'personalization_elements': []
        }

        # Determine tone based on profile
        if prospect.bio:
            bio_lower = prospect.bio.lower()
            if any(word in bio_lower for word in ['passionate', 'excited', 'love', 'awesome']):
                strategy['tone_recommendation'] = 'enthusiastic'
            elif any(word in bio_lower for word in ['research', 'academic', 'paper']):
                strategy['tone_recommendation'] = 'academic'

        # Personalization elements
        if prospect.language:
            strategy['personalization_elements'].append(f"Reference {prospect.language} expertise")
        if prospect.repo_full_name:
            strategy['personalization_elements'].append("Mention specific repository work")
        if prospect.company:
            strategy['personalization_elements'].append("Acknowledge company context")

        # Follow-up sequence
        strategy['follow_up_sequence'] = [
            {'day': 3, 'type': 'value_add_email', 'content': 'Share relevant resource'},
            {'day': 7, 'type': 'question_email', 'content': 'Ask about their work'},
            {'day': 14, 'type': 'final_followup', 'content': 'Last attempt with different angle'}
        ]

        return strategy

    def _assess_outreach_risks(self, prospect: 'ProspectData') -> Dict[str, Any]:
        """Assess risks associated with outreach"""

        risks = {
            'overall_risk_level': 'low',
            'specific_risks': [],
            'mitigation_strategies': [],
            'success_probability': 0.7
        }

        # Risk assessment
        risk_factors = []

        # Low activity risk
        if not prospect.contributions_last_year or prospect.contributions_last_year < 5:
            risk_factors.append('low_recent_activity')
            risks['mitigation_strategies'].append('Focus on long-term relationship building')

        # No company context
        if not prospect.company:
            risk_factors.append('limited_company_context')
            risks['mitigation_strategies'].append('Research company through other means')

        # Generic email risk
        best_email = prospect.get_best_email()
        if best_email and ('gmail.com' in best_email or 'yahoo.com' in best_email):
            risk_factors.append('personal_email_only')
            risks['mitigation_strategies'].append('Consider LinkedIn outreach as alternative')

        # Determine risk level
        if len(risk_factors) >= 3:
            risks['overall_risk_level'] = 'high'
            risks['success_probability'] = 0.4
        elif len(risk_factors) >= 2:
            risks['overall_risk_level'] = 'medium'
            risks['success_probability'] = 0.5
        else:
            risks['overall_risk_level'] = 'low'
            risks['success_probability'] = 0.7

        risks['specific_risks'] = risk_factors

        return risks

    def _calculate_opportunity_score(self, insights: Dict[str, Any]) -> float:
        """Calculate overall opportunity score (0-100)"""

        score = 50  # Base score

        # Profile analysis boost
        profile = insights.get('profile_analysis', {})
        if profile.get('professional_level') == 'expert':
            score += 20
        elif profile.get('professional_level') == 'advanced':
            score += 10

        if profile.get('network_influence') == 'high':
            score += 15
        elif profile.get('network_influence') == 'medium':
            score += 8

        # Engagement prediction boost
        engagement = insights.get('engagement_prediction', {})
        if engagement.get('overall_potential') == 'high':
            score += 15
        elif engagement.get('overall_potential') == 'low':
            score -= 10

        response_likelihood = engagement.get('response_likelihood', 0.5)
        score += (response_likelihood - 0.5) * 20

        # Risk assessment penalty
        risk = insights.get('risk_assessment', {})
        if risk.get('overall_risk_level') == 'high':
            score -= 15
        elif risk.get('overall_risk_level') == 'medium':
            score -= 8

        return max(0, min(100, score))

    def _get_cached_insights(self, prospect_id: str) -> Optional[Dict[str, Any]]:
        """Get cached insights if available"""

        cache_file = os.path.join(self.insights_dir, f"{prospect_id}_insights.json")

        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    cached = json.load(f)

                # Check if cache is still valid (7 days)
                cached_time = datetime.fromisoformat(cached['generated_at'])
                if (datetime.now() - cached_time).total_seconds() < 604800:  # 7 days
                    return cached

            except Exception as e:
                logger.warning(f"Error reading cached insights: {e}")

        return None

    def _cache_insights(self, prospect_id: str, insights: Dict[str, Any]) -> None:
        """Cache insights"""

        cache_file = os.path.join(self.insights_dir, f"{prospect_id}_insights.json")

        try:
            with open(cache_file, 'w') as f:
                json.dump(insights, f, indent=2)
        except Exception as e:
            logger.warning(f"Error caching insights: {e}")

    def generate_prospect_portfolio_analysis(self, prospect_ids: List[str]) -> Dict[str, Any]:
        """Generate portfolio analysis for multiple prospects"""

        insights = []
        for prospect_id in prospect_ids:
            prospect = self.storage.get_prospect(prospect_id)
            if prospect:
                insight = self.generate_comprehensive_insights(prospect.__dict__)
                insights.append(insight)

        if not insights:
            return {'error': 'No valid prospects found'}

        # Aggregate analysis
        analysis = {
            'portfolio_size': len(insights),
            'average_opportunity_score': sum(i.get('opportunity_score', 0) for i in insights) / len(insights),
            'high_potential_count': len([i for i in insights if i.get('opportunity_score', 0) > 70]),
            'medium_potential_count': len([i for i in insights if 40 <= i.get('opportunity_score', 0) <= 70]),
            'low_potential_count': len([i for i in insights if i.get('opportunity_score', 0) < 40]),
            'top_opportunities': sorted(insights, key=lambda x: x.get('opportunity_score', 0), reverse=True)[:5],
            'risk_distribution': self._analyze_portfolio_risks(insights),
            'engagement_predictions': self._aggregate_engagement_predictions(insights)
        }

        return analysis

    def _analyze_portfolio_risks(self, insights: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze risk distribution across portfolio"""

        risk_levels = {'high': 0, 'medium': 0, 'low': 0}

        for insight in insights:
            risk_level = insight.get('risk_assessment', {}).get('overall_risk_level', 'medium')
            risk_levels[risk_level] += 1

        return {
            'distribution': risk_levels,
            'high_risk_percentage': risk_levels['high'] / len(insights) if insights else 0,
            'risk_mitigation_needed': risk_levels['high'] > len(insights) * 0.2
        }

    def _aggregate_engagement_predictions(self, insights: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate engagement predictions across portfolio"""

        predictions = [i.get('engagement_prediction', {}) for i in insights]

        avg_response_likelihood = sum(p.get('response_likelihood', 0) for p in predictions) / len(predictions) if predictions else 0

        potential_distribution = defaultdict(int)
        for insight in insights:
            potential = insight.get('engagement_prediction', {}).get('overall_potential', 'medium')
            potential_distribution[potential] += 1

        return {
            'average_response_likelihood': round(avg_response_likelihood, 3),
            'potential_distribution': dict(potential_distribution),
            'portfolio_engagement_score': round(avg_response_likelihood * 100, 1)
        }

    def generate_outreach_recommendations(self, prospect_id: str) -> Dict[str, Any]:
        """Generate specific outreach recommendations for a prospect"""

        prospect = self.storage.get_prospect(prospect_id)
        if not prospect:
            return {'error': f'Prospect {prospect_id} not found'}

        insights = self.generate_comprehensive_insights(prospect.__dict__)

        recommendations = {
            'prospect_id': prospect_id,
            'immediate_actions': [],
            'timing_recommendations': [],
            'channel_strategy': [],
            'content_suggestions': [],
            'follow_up_plan': []
        }

        # Immediate actions
        if insights.get('engagement_prediction', {}).get('overall_potential') == 'high':
            recommendations['immediate_actions'].append('Prioritize for immediate outreach')

        if insights.get('opportunity_score', 0) > 70:
            recommendations['immediate_actions'].append('Flag as high-priority opportunity')

        # Timing recommendations
        engagement = insights.get('engagement_prediction', {})
        if engagement.get('optimal_timing'):
            recommendations['timing_recommendations'].append(engagement['optimal_timing'])

        # Channel strategy
        outreach = insights.get('outreach_recommendations', {})
        recommendations['channel_strategy'] = outreach.get('channel_mix', ['email'])

        # Content suggestions
        strategy = outreach.get('outreach_strategy', {})
        if strategy.get('tone_recommendation'):
            recommendations['content_suggestions'].append(f"Use {strategy['tone_recommendation']} tone")

        if strategy.get('personalization_elements'):
            recommendations['content_suggestions'].extend(strategy['personalization_elements'])

        # Follow-up plan
        if strategy.get('follow_up_sequence'):
            recommendations['follow_up_plan'] = strategy['follow_up_sequence']

        return recommendations
