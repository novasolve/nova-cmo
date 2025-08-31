#!/usr/bin/env python3
"""
AI-Powered Copy Optimization and A/B Testing System
Optimizes copy performance using AI analysis and testing
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import statistics
import random

from .ai_copy_generator import AICopyGenerator
from .content_analyzer import ContentAnalyzer
from .core.models import ProspectData, ICPProfile

logger = logging.getLogger(__name__)


class CopyOptimizer:
    """AI-powered copy optimization and A/B testing"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.ai_generator = AICopyGenerator(api_key)
        self.content_analyzer = ContentAnalyzer(api_key)
        self.logger = logger

        # Performance tracking
        self.performance_data_dir = "copy_factory/data/performance"
        os.makedirs(self.performance_data_dir, exist_ok=True)

        # Optimization models
        self.optimization_history_dir = "copy_factory/data/optimization"
        os.makedirs(self.optimization_history_dir, exist_ok=True)

    def generate_ab_test_variants(self, base_copy: Dict[str, Any],
                                prospect: ProspectData, icp: ICPProfile,
                                num_variants: int = 3) -> List[Dict[str, Any]]:
        """Generate A/B test variants of copy"""

        variants = []

        # Always include the original as variant A
        variants.append({
            'variant_id': 'A',
            'subject': base_copy.get('subject', ''),
            'body': base_copy.get('body', ''),
            'tone': base_copy.get('tone', 'professional'),
            'strategy': 'original',
            'generated_at': datetime.now().isoformat()
        })

        # Generate optimized variants
        for i in range(num_variants - 1):
            variant_id = chr(ord('B') + i)

            # Use different optimization strategies
            strategies = ['concise', 'benefit_focused', 'question_driven', 'social_proof', 'urgency']
            strategy = strategies[i % len(strategies)]

            optimized = self._generate_optimized_variant(
                base_copy, prospect, icp, strategy
            )

            variants.append({
                'variant_id': variant_id,
                'subject': optimized.get('subject', ''),
                'body': optimized.get('body', ''),
                'tone': optimized.get('tone', base_copy.get('tone', 'professional')),
                'strategy': strategy,
                'generated_at': datetime.now().isoformat()
            })

        return variants

    def _generate_optimized_variant(self, base_copy: Dict[str, Any],
                                  prospect: ProspectData, icp: ICPProfile,
                                  strategy: str) -> Dict[str, Any]:
        """Generate an optimized variant using specific strategy"""

        strategy_prompts = {
            'concise': "Make this copy more concise while keeping key points",
            'benefit_focused': "Focus on benefits and outcomes rather than features",
            'question_driven': "Use questions to engage and build curiosity",
            'social_proof': "Add elements of social proof and credibility",
            'urgency': "Create a sense of timely opportunity or limited availability"
        }

        prompt = f"""Optimize this outreach copy using the {strategy} strategy:

STRATEGY: {strategy_prompts.get(strategy, strategy)}

ORIGINAL SUBJECT: {base_copy.get('subject', '')}
ORIGINAL BODY: {base_copy.get('body', '')}

PROSPECT CONTEXT: {prospect.name or 'Unknown'}, {prospect.company or 'Unknown company'}, {prospect.language or 'Unknown tech'}

Optimize for:
- Higher engagement potential
- Clearer value proposition
- Better personalization
- More compelling call-to-action

Return optimized version in same format:
SUBJECT: [optimized subject]
BODY: [optimized body]
"""

        try:
            response = self.ai_generator._call_ai_api(prompt)
            subject, body = self.ai_generator._parse_ai_response(response)

            return {
                'subject': subject,
                'body': body,
                'tone': base_copy.get('tone', 'professional'),
                'strategy': strategy
            }

        except Exception as e:
            self.logger.error(f"Variant generation failed: {e}")
            return base_copy

    def run_ab_test(self, variants: List[Dict[str, Any]], test_duration_days: int = 7) -> Dict[str, Any]:
        """Run A/B test simulation and analysis"""

        # Simulate test results (in real implementation, this would track actual performance)
        test_results = self._simulate_ab_test_results(variants, test_duration_days)

        # Analyze results
        analysis = self._analyze_ab_test_results(test_results)

        # Generate recommendations
        recommendations = self._generate_ab_recommendations(analysis)

        return {
            'test_id': f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'variants_tested': len(variants),
            'test_duration_days': test_duration_days,
            'results': test_results,
            'analysis': analysis,
            'recommendations': recommendations,
            'winner': analysis.get('winner_variant'),
            'confidence_level': analysis.get('confidence_level'),
            'test_completed_at': datetime.now().isoformat()
        }

    def _simulate_ab_test_results(self, variants: List[Dict[str, Any]],
                                duration_days: int) -> Dict[str, Any]:
        """Simulate A/B test results (placeholder for real tracking)"""

        # Simulate realistic performance data
        base_performance = {
            'A': {'open_rate': 0.25, 'response_rate': 0.03, 'conversion_rate': 0.005}
        }

        # Generate performance for other variants with some variation
        for variant in variants[1:]:  # Skip variant A
            variant_id = variant['variant_id']
            strategy = variant['strategy']

            # Different strategies have different performance characteristics
            strategy_multipliers = {
                'concise': {'open_rate': 1.1, 'response_rate': 1.05, 'conversion_rate': 1.02},
                'benefit_focused': {'open_rate': 1.15, 'response_rate': 1.2, 'conversion_rate': 1.25},
                'question_driven': {'open_rate': 1.08, 'response_rate': 1.15, 'conversion_rate': 1.1},
                'social_proof': {'open_rate': 1.05, 'response_rate': 1.08, 'conversion_rate': 1.12},
                'urgency': {'open_rate': 1.12, 'response_rate': 1.05, 'conversion_rate': 1.08}
            }

            multipliers = strategy_multipliers.get(strategy, {'open_rate': 1.0, 'response_rate': 1.0, 'conversion_rate': 1.0})

            base_performance[variant_id] = {
                'open_rate': base_performance['A']['open_rate'] * multipliers['open_rate'] * random.uniform(0.9, 1.1),
                'response_rate': base_performance['A']['response_rate'] * multipliers['response_rate'] * random.uniform(0.9, 1.1),
                'conversion_rate': base_performance['A']['conversion_rate'] * multipliers['conversion_rate'] * random.uniform(0.9, 1.1)
            }

        return base_performance

    def _analyze_ab_test_results(self, test_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze A/B test results"""

        # Find winner based on conversion rate (most important metric)
        conversion_rates = {vid: data['conversion_rate'] for vid, data in test_results.items()}
        winner_variant = max(conversion_rates.items(), key=lambda x: x[1])[0]

        # Calculate statistical significance (simplified)
        rates = list(conversion_rates.values())
        winner_rate = conversion_rates[winner_variant]
        avg_other_rates = statistics.mean([r for r in rates if r != winner_rate])

        improvement = (winner_rate - avg_other_rates) / avg_other_rates if avg_other_rates > 0 else 0

        confidence_level = "high" if improvement > 0.2 else "medium" if improvement > 0.1 else "low"

        # Performance by metric
        metrics_analysis = {}
        for metric in ['open_rate', 'response_rate', 'conversion_rate']:
            metric_data = {vid: data[metric] for vid, data in test_results.items()}
            best_variant = max(metric_data.items(), key=lambda x: x[1])[0]
            best_value = metric_data[best_variant]

            metrics_analysis[metric] = {
                'best_variant': best_variant,
                'best_value': round(best_value, 4),
                'improvement_over_baseline': round((best_value - test_results['A'][metric]) / test_results['A'][metric], 3)
            }

        return {
            'winner_variant': winner_variant,
            'winner_conversion_rate': round(conversion_rates[winner_variant], 4),
            'average_improvement': round(improvement, 3),
            'confidence_level': confidence_level,
            'metrics_analysis': metrics_analysis,
            'recommendations': self._generate_analysis_recommendations(metrics_analysis)
        }

    def _generate_analysis_recommendations(self, metrics_analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on analysis"""

        recommendations = []

        # Overall winner
        winner = metrics_analysis['conversion_rate']['best_variant']
        if winner != 'A':
            recommendations.append(f"Variant {winner} shows best overall performance - consider adopting its strategy")

        # Metric-specific insights
        if metrics_analysis['open_rate']['improvement_over_baseline'] > 0.1:
            best_open = metrics_analysis['open_rate']['best_variant']
            recommendations.append(f"Variant {best_open} significantly improves open rates - focus on subject line optimization")

        if metrics_analysis['response_rate']['improvement_over_baseline'] > 0.15:
            best_response = metrics_analysis['response_rate']['best_variant']
            recommendations.append(f"Variant {best_response} dramatically improves response rates - study its engagement techniques")

        # Strategy insights
        if all(metrics_analysis[metric]['improvement_over_baseline'] > 0.05 for metric in ['open_rate', 'response_rate', 'conversion_rate']):
            recommendations.append("All variants show improvement - consider implementing multiple optimization strategies")

        return recommendations

    def _generate_ab_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate final recommendations from A/B test"""

        recommendations = []

        winner = analysis.get('winner_variant')
        confidence = analysis.get('confidence_level')

        if winner and winner != 'A':
            recommendations.append(f"🎯 Adopt variant {winner} as the new baseline - it shows {analysis.get('average_improvement', 0)*100:.1f}% improvement")

        if confidence == 'high':
            recommendations.append("📊 High confidence in results - implement changes immediately")
        elif confidence == 'medium':
            recommendations.append("📊 Medium confidence - consider running follow-up test to confirm")
        else:
            recommendations.append("📊 Low confidence - run longer test or with larger sample size")

        # Strategy recommendations
        metrics = analysis.get('metrics_analysis', {})
        if metrics.get('open_rate', {}).get('improvement_over_baseline', 0) > 0.1:
            recommendations.append("📧 Focus on subject line optimization for future campaigns")

        if metrics.get('response_rate', {}).get('improvement_over_baseline', 0) > 0.15:
            recommendations.append("💬 Study successful variants for engagement techniques")

        return recommendations

    def optimize_copy_for_target_audience(self, base_copy: Dict[str, Any],
                                        prospects: List[ProspectData],
                                        icp: ICPProfile) -> Dict[str, Any]:
        """Optimize copy based on target audience analysis"""

        # Analyze the target audience
        audience_analysis = self._analyze_target_audience(prospects)

        # Generate optimization prompt based on audience insights
        prompt = f"""Optimize this copy for the target audience:

AUDIENCE ANALYSIS:
- Average experience: {audience_analysis['avg_experience']}
- Primary interests: {', '.join(audience_analysis['top_interests'])}
- Communication preferences: {audience_analysis['comm_preferences']}
- Pain points: {', '.join(audience_analysis['pain_points'])}
- Company sizes: {audience_analysis['company_size_distribution']}

ORIGINAL COPY:
Subject: {base_copy.get('subject', '')}
Body: {base_copy.get('body', '')}

Optimize for:
1. Audience experience level
2. Key interests and pain points
3. Communication style preferences
4. Company size context
5. Industry-specific language

Return optimized version:
SUBJECT: [optimized subject]
BODY: [optimized body]
"""

        try:
            response = self.ai_generator._call_ai_api(prompt)
            subject, body = self.ai_generator._parse_ai_response(response)

            return {
                'subject': subject,
                'body': body,
                'optimization_type': 'audience_targeted',
                'audience_insights': audience_analysis,
                'improvement_factors': ['experience_level', 'interests', 'communication_style', 'company_context']
            }

        except Exception as e:
            self.logger.error(f"Audience optimization failed: {e}")
            return base_copy

    def _analyze_target_audience(self, prospects: List[ProspectData]) -> Dict[str, Any]:
        """Analyze target audience characteristics"""

        if not prospects:
            return {}

        # Analyze experience levels
        experience_levels = []
        for prospect in prospects:
            # Estimate experience from various signals
            experience_score = 0

            if prospect.contributions_last_year is not None and prospect.contributions_last_year > 50:
                experience_score += 2
            if prospect.followers is not None and prospect.followers > 100:
                experience_score += 1
            if prospect.public_repos is not None and prospect.public_repos > 20:
                experience_score += 1

            if experience_score >= 3:
                experience_levels.append('senior')
            elif experience_score >= 1:
                experience_levels.append('mid')
            else:
                experience_levels.append('junior')

        # Find most common experience level
        avg_experience = max(set(experience_levels), key=experience_levels.count) if experience_levels else 'unknown'

        # Analyze interests
        all_interests = []
        for prospect in prospects:
            if prospect.topics:
                all_interests.extend(prospect.topics)

        top_interests = [interest for interest, count in
                        sorted(Counter(all_interests).items(), key=lambda x: x[1], reverse=True)][:5]

        # Communication preferences (simplified)
        comm_preferences = "technical, professional"

        # Pain points (simplified)
        pain_points = ["scalability", "performance", "maintenance"]

        # Company size distribution
        company_sizes = ["small", "medium", "large"]

        return {
            'avg_experience': avg_experience,
            'top_interests': top_interests,
            'comm_preferences': comm_preferences,
            'pain_points': pain_points,
            'company_size_distribution': company_sizes,
            'audience_size': len(prospects)
        }

    def learn_from_performance_data(self, historical_performance: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Learn from historical performance data to improve future optimizations"""

        if not historical_performance:
            return {}

        # Analyze patterns in successful copy
        successful_patterns = self._analyze_successful_patterns(historical_performance)

        # Extract winning strategies
        winning_strategies = self._extract_winning_strategies(historical_performance)

        # Build optimization model
        optimization_model = self._build_optimization_model(successful_patterns, winning_strategies)

        return {
            'successful_patterns': successful_patterns,
            'winning_strategies': winning_strategies,
            'optimization_model': optimization_model,
            'model_version': datetime.now().strftime('%Y%m%d'),
            'training_data_size': len(historical_performance)
        }

    def _analyze_successful_patterns(self, performance_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze patterns in successful copy"""

        successful_copy = [data for data in performance_data if data.get('conversion_rate', 0) > 0.01]

        patterns = {
            'avg_word_count': statistics.mean([len(data.get('body', '').split()) for data in successful_copy]) if successful_copy else 0,
            'common_phrases': self._extract_common_phrases(successful_copy),
            'successful_tones': Counter([data.get('tone', 'professional') for data in successful_copy]),
            'effective_strategies': Counter([data.get('strategy', 'original') for data in successful_copy])
        }

        return patterns

    def _extract_common_phrases(self, copy_data: List[Dict[str, Any]]) -> List[str]:
        """Extract common phrases from successful copy"""

        # Simple implementation - extract common short phrases
        phrases = []
        for data in copy_data:
            body = data.get('body', '').lower()
            # Extract 2-3 word phrases
            words = body.split()
            for i in range(len(words) - 1):
                phrase = ' '.join(words[i:i+2])
                if len(phrase) > 10:  # Meaningful phrases
                    phrases.append(phrase)

        return [phrase for phrase, count in Counter(phrases).most_common(10)]

    def _extract_winning_strategies(self, performance_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract strategies that consistently win"""

        strategy_performance = defaultdict(list)

        for data in performance_data:
            strategy = data.get('strategy', 'original')
            conversion = data.get('conversion_rate', 0)
            strategy_performance[strategy].append(conversion)

        winning_strategies = {}
        for strategy, conversions in strategy_performance.items():
            if len(conversions) >= 3:  # Need at least 3 data points
                avg_conversion = statistics.mean(conversions)
                winning_strategies[strategy] = {
                    'avg_conversion': round(avg_conversion, 4),
                    'sample_size': len(conversions),
                    'consistency': statistics.stdev(conversions) if len(conversions) > 1 else 0
                }

        return dict(sorted(winning_strategies.items(), key=lambda x: x[1]['avg_conversion'], reverse=True))

    def _build_optimization_model(self, patterns: Dict[str, Any],
                                strategies: Dict[str, Any]) -> Dict[str, Any]:
        """Build optimization model from learned patterns"""

        model = {
            'recommended_tones': list(patterns.get('successful_tones', {}).keys())[:3],
            'recommended_strategies': list(strategies.keys())[:3],
            'optimal_word_count': {
                'min': max(50, patterns.get('avg_word_count', 100) - 50),
                'max': patterns.get('avg_word_count', 100) + 50,
                'target': patterns.get('avg_word_count', 100)
            },
            'effective_phrases': patterns.get('common_phrases', [])[:5],
            'confidence_score': min(1.0, len(strategies) * 0.1)  # Simple confidence calculation
        }

        return model

    def apply_learned_optimizations(self, base_copy: Dict[str, Any],
                                  optimization_model: Dict[str, Any]) -> Dict[str, Any]:
        """Apply learned optimizations to new copy"""

        if not optimization_model:
            return base_copy

        prompt = f"""Optimize this copy using learned performance patterns:

LEARNED PATTERNS:
- Optimal word count: {optimization_model.get('optimal_word_count', {}).get('target', 100)}
- Effective phrases: {', '.join(optimization_model.get('effective_phrases', []))}
- Recommended tones: {', '.join(optimization_model.get('recommended_tones', []))}
- Winning strategies: {', '.join(optimization_model.get('recommended_strategies', []))}

ORIGINAL COPY:
Subject: {base_copy.get('subject', '')}
Body: {base_copy.get('body', '')}

Apply optimizations based on successful patterns:
"""

        try:
            response = self.ai_generator._call_ai_api(prompt)
            subject, body = self.ai_generator._parse_ai_response(response)

            return {
                'subject': subject,
                'body': body,
                'optimization_applied': 'learned_patterns',
                'model_used': optimization_model,
                'improvement_confidence': optimization_model.get('confidence_score', 0)
            }

        except Exception as e:
            self.logger.error(f"Learned optimization failed: {e}")
            return base_copy

    def save_performance_data(self, performance_data: Dict[str, Any]) -> None:
        """Save performance data for future learning"""

        filename = f"performance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self.performance_data_dir, filename)

        try:
            with open(filepath, 'w') as f:
                json.dump(performance_data, f, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save performance data: {e}")

    def load_historical_performance(self, days_back: int = 30) -> List[Dict[str, Any]]:
        """Load historical performance data"""

        import glob

        pattern = os.path.join(self.performance_data_dir, "performance_*.json")
        files = glob.glob(pattern)

        # Filter by date
        cutoff_date = datetime.now() - timedelta(days=days_back)
        recent_files = []

        for file in files:
            try:
                # Extract date from filename
                date_str = file.split('_')[1].split('.')[0]  # Extract date part
                file_date = datetime.strptime(date_str, '%Y%m%d')
                if file_date >= cutoff_date:
                    recent_files.append(file)
            except:
                continue

        # Load data from recent files
        historical_data = []
        for file in recent_files[-50:]:  # Limit to last 50 files
            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                    historical_data.append(data)
            except Exception as e:
                self.logger.warning(f"Error loading performance data from {file}: {e}")

        return historical_data

