#!/usr/bin/env python3
"""
Performance Tracking and AI-Driven Optimization System
Tracks campaign performance and uses AI to continuously improve results
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import statistics
import numpy as np

from .ai_copy_generator import AICopyGenerator
from .copy_optimizer import CopyOptimizer
from .campaign_automator import CampaignAutomator
from .core.storage import CopyFactoryStorage

logger = logging.getLogger(__name__)


class PerformanceTracker:
    """Tracks and analyzes campaign performance data"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.ai_generator = AICopyGenerator(api_key)
        self.storage = CopyFactoryStorage()

        # Performance data storage
        self.performance_dir = "copy_factory/data/performance"
        os.makedirs(self.performance_dir, exist_ok=True)

        # Learning data storage
        self.learning_dir = "copy_factory/data/learning"
        os.makedirs(self.learning_dir, exist_ok=True)

    def track_campaign_performance(self, campaign_id: str, performance_data: Dict[str, Any]) -> Dict[str, Any]:
        """Track performance data for a campaign"""

        # Add metadata
        performance_data.update({
            'campaign_id': campaign_id,
            'tracked_at': datetime.now().isoformat(),
            'tracking_version': '1.0'
        })

        # Save performance data
        filename = f"performance_{campaign_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = os.path.join(self.performance_dir, filename)

        try:
            with open(filepath, 'w') as f:
                json.dump(performance_data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save performance data: {e}")
            return {'error': str(e)}

        # Update campaign status if needed
        self._update_campaign_status(campaign_id, performance_data)

        return {
            'status': 'tracked',
            'campaign_id': campaign_id,
            'data_points': len(performance_data),
            'filename': filename
        }

    def _update_campaign_status(self, campaign_id: str, performance_data: Dict[str, Any]):
        """Update campaign status based on performance"""

        campaign = self.storage.get_campaign(campaign_id)
        if not campaign:
            return

        # Determine status based on performance
        sent = performance_data.get('emails_sent', 0)
        responses = performance_data.get('responses', 0)

        if sent == 0:
            new_status = 'draft'
        elif responses > 0:
            new_status = 'active'
        elif sent > 0:
            new_status = 'running'
        else:
            new_status = 'completed'

        if campaign.status != new_status:
            campaign.status = new_status
            campaign.updated_at = datetime.now()
            self.storage.save_campaign(campaign)

    def analyze_performance_trends(self, campaign_ids: Optional[List[str]] = None,
                                  days_back: int = 30) -> Dict[str, Any]:
        """Analyze performance trends across campaigns"""

        # Get performance data
        performance_files = self._get_performance_files(campaign_ids, days_back)
        performance_data = []

        for file_path in performance_files:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    performance_data.append(data)
            except Exception as e:
                logger.warning(f"Error loading performance data from {file_path}: {e}")

        if not performance_data:
            return {'error': 'No performance data found'}

        # Analyze trends
        trends = self._calculate_performance_trends(performance_data)

        # Generate insights
        insights = self._generate_performance_insights(trends)

        # Identify optimization opportunities
        opportunities = self._identify_optimization_opportunities(trends)

        return {
            'analysis_period': f"{days_back} days",
            'campaigns_analyzed': len(set(d['campaign_id'] for d in performance_data)),
            'total_data_points': len(performance_data),
            'trends': trends,
            'insights': insights,
            'optimization_opportunities': opportunities,
            'recommendations': self._generate_trend_recommendations(trends)
        }

    def _get_performance_files(self, campaign_ids: Optional[List[str]], days_back: int) -> List[str]:
        """Get relevant performance files"""

        import glob

        pattern = os.path.join(self.performance_dir, "performance_*.json")
        all_files = glob.glob(pattern)

        # Filter by campaign if specified
        if campaign_ids:
            filtered_files = []
            for file_path in all_files:
                for campaign_id in campaign_ids:
                    if campaign_id in file_path:
                        filtered_files.append(file_path)
                        break
            all_files = filtered_files

        # Filter by date
        cutoff_date = datetime.now() - timedelta(days=days_back)
        recent_files = []

        for file_path in all_files:
            try:
                # Extract date from filename
                parts = os.path.basename(file_path).split('_')
                if len(parts) >= 3:
                    date_str = parts[2].split('.')[0]  # Remove .json
                    if len(date_str) >= 8:  # YYYYMMDD format
                        file_date = datetime.strptime(date_str[:8], '%Y%m%d')
                        if file_date >= cutoff_date:
                            recent_files.append(file_path)
            except:
                # If date parsing fails, include the file
                recent_files.append(file_path)

        return recent_files

    def _calculate_performance_trends(self, performance_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate performance trends from data"""

        if not performance_data:
            return {}

        # Group by metric
        metrics_data = defaultdict(list)

        for data in performance_data:
            sent = data.get('emails_sent', 0)
            if sent > 0:
                metrics_data['open_rate'].append(data.get('opens', 0) / sent)
                metrics_data['response_rate'].append(data.get('responses', 0) / sent)
                metrics_data['conversion_rate'].append(data.get('conversions', 0) / sent)
                metrics_data['bounce_rate'].append(data.get('bounces', 0) / sent)

        # Calculate statistics for each metric
        trends = {}
        for metric, values in metrics_data.items():
            if values:
                trends[metric] = {
                    'average': round(statistics.mean(values), 4),
                    'median': round(statistics.median(values), 4),
                    'min': round(min(values), 4),
                    'max': round(max(values), 4),
                    'std_dev': round(statistics.stdev(values), 4) if len(values) > 1 else 0,
                    'sample_size': len(values),
                    'trend_direction': self._calculate_trend_direction(values)
                }

        return trends

    def _calculate_trend_direction(self, values: List[float]) -> str:
        """Calculate if metric is trending up, down, or stable"""

        if len(values) < 3:
            return 'insufficient_data'

        # Simple trend calculation using linear regression
        x = list(range(len(values)))
        y = values

        # Calculate slope
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_xx = sum(xi * xi for xi in x)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x)

        if slope > 0.001:
            return 'improving'
        elif slope < -0.001:
            return 'declining'
        else:
            return 'stable'

    def _generate_performance_insights(self, trends: Dict[str, Any]) -> List[str]:
        """Generate insights from performance trends"""

        insights = []

        # Analyze key metrics
        open_rate = trends.get('open_rate', {})
        response_rate = trends.get('response_rate', {})
        conversion_rate = trends.get('conversion_rate', {})

        if open_rate:
            avg_open = open_rate.get('average', 0)
            if avg_open > 0.25:
                insights.append(f"Strong open rates ({avg_open:.1%}) indicate compelling subject lines")
            elif avg_open < 0.15:
                insights.append(f"Open rates ({avg_open:.1%}) need improvement - consider subject line optimization")

        if response_rate:
            avg_response = response_rate.get('average', 0)
            if avg_response > 0.03:
                insights.append(f"Good response rates ({avg_response:.1%}) show effective copy and targeting")
            elif avg_response < 0.01:
                insights.append(f"Response rates ({avg_response:.1%}) indicate need for copy or targeting improvements")

        if conversion_rate:
            avg_conversion = conversion_rate.get('average', 0)
            trend = conversion_rate.get('trend_direction')
            if trend == 'improving':
                insights.append("Conversion rates are improving - current strategies are working")
            elif trend == 'declining':
                insights.append("Conversion rates are declining - review recent changes")

        # Overall performance assessment
        if all(trends.get(metric, {}).get('trend_direction') == 'improving'
               for metric in ['open_rate', 'response_rate', 'conversion_rate']):
            insights.append("All key metrics are improving - campaigns are performing well")
        elif all(trends.get(metric, {}).get('trend_direction') == 'declining'
                for metric in ['open_rate', 'response_rate', 'conversion_rate']):
            insights.append("Multiple metrics are declining - comprehensive review needed")

        return insights

    def _identify_optimization_opportunities(self, trends: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Identify specific optimization opportunities"""

        opportunities = []

        # Subject line optimization
        open_rate = trends.get('open_rate', {})
        if open_rate and open_rate.get('average', 0) < 0.2:
            opportunities.append({
                'type': 'subject_line_optimization',
                'priority': 'high',
                'description': 'Open rates below optimal threshold',
                'current_value': open_rate.get('average', 0),
                'target': 0.25,
                'actions': ['A/B test subject lines', 'Use personalization', 'Create urgency']
            })

        # Copy optimization
        response_rate = trends.get('response_rate', {})
        if response_rate and response_rate.get('average', 0) < 0.02:
            opportunities.append({
                'type': 'copy_optimization',
                'priority': 'high',
                'description': 'Response rates indicate copy needs improvement',
                'current_value': response_rate.get('average', 0),
                'target': 0.03,
                'actions': ['Test different copy tones', 'Focus on benefits', 'Add social proof']
            })

        # Targeting optimization
        conversion_rate = trends.get('conversion_rate', {})
        if conversion_rate and conversion_rate.get('average', 0) < 0.005:
            opportunities.append({
                'type': 'targeting_optimization',
                'priority': 'medium',
                'description': 'Low conversion rates suggest targeting issues',
                'current_value': conversion_rate.get('average', 0),
                'target': 0.01,
                'actions': ['Refine ICP matching', 'Review prospect quality', 'Adjust campaign goals']
            })

        return opportunities

    def _generate_trend_recommendations(self, trends: Dict[str, Any]) -> List[str]:
        """Generate actionable recommendations based on trends"""

        recommendations = []

        # Based on metric performance
        if trends.get('open_rate', {}).get('average', 0) < 0.2:
            recommendations.append("Implement A/B testing for subject lines with higher personalization")

        if trends.get('response_rate', {}).get('trend_direction') == 'declining':
            recommendations.append("Review recent copy changes that may have impacted response rates")

        if trends.get('conversion_rate', {}).get('std_dev', 0) > 0.005:
            recommendations.append("High conversion rate variance suggests inconsistent prospect quality")

        # Timing recommendations
        recommendations.append("Consider testing different send times and days for optimal engagement")

        # Content recommendations
        recommendations.append("Experiment with different value propositions and call-to-action placements")

        return recommendations


class AIDrivenOptimizer:
    """AI-driven optimization system that learns from performance"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.ai_generator = AICopyGenerator(api_key)
        self.performance_tracker = PerformanceTracker(api_key)
        self.copy_optimizer = CopyOptimizer(api_key)

        # Learning model storage
        self.model_dir = "copy_factory/data/models"
        os.makedirs(self.model_dir, exist_ok=True)

    def learn_from_performance(self, historical_performance: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Learn optimization patterns from historical performance"""

        if not historical_performance:
            return {'error': 'No performance data available for learning'}

        # Analyze successful patterns
        successful_patterns = self._analyze_success_patterns(historical_performance)

        # Build optimization model
        optimization_model = self._build_learning_model(successful_patterns)

        # Save the model
        model_file = os.path.join(self.model_dir, f"optimization_model_{datetime.now().strftime('%Y%m%d')}.json")

        try:
            with open(model_file, 'w') as f:
                json.dump({
                    'model': optimization_model,
                    'created_at': datetime.now().isoformat(),
                    'training_data_size': len(historical_performance),
                    'model_version': '1.0'
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save optimization model: {e}")

        return {
            'status': 'learned',
            'patterns_found': len(successful_patterns),
            'model_saved': model_file,
            'optimization_model': optimization_model
        }

    def _analyze_success_patterns(self, performance_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze patterns in successful campaigns"""

        # Define success criteria
        successful_campaigns = []
        for data in performance_data:
            sent = data.get('emails_sent', 0)
            responses = data.get('responses', 0)
            conversions = data.get('conversions', 0)

            if sent > 0:
                response_rate = responses / sent
                conversion_rate = conversions / sent

                # Consider successful if above thresholds
                if response_rate > 0.02 or conversion_rate > 0.005:
                    successful_campaigns.append(data)

        patterns = {
            'successful_campaigns': len(successful_campaigns),
            'avg_response_rate': 0,
            'avg_conversion_rate': 0,
            'common_characteristics': [],
            'winning_strategies': []
        }

        if successful_campaigns:
            response_rates = [data.get('responses', 0) / data.get('emails_sent', 1) for data in successful_campaigns]
            conversion_rates = [data.get('conversions', 0) / data.get('emails_sent', 1) for data in successful_campaigns]

            patterns['avg_response_rate'] = statistics.mean(response_rates)
            patterns['avg_conversion_rate'] = statistics.mean(conversion_rates)

            # Analyze common characteristics
            patterns['common_characteristics'] = self._find_common_characteristics(successful_campaigns)

        return patterns

    def _find_common_characteristics(self, successful_campaigns: List[Dict[str, Any]]) -> List[str]:
        """Find common characteristics in successful campaigns"""

        characteristics = []

        # Analyze timing patterns
        send_times = [data.get('send_time') for data in successful_campaigns if data.get('send_time')]
        if send_times:
            # This would analyze optimal send times
            characteristics.append("Optimal send timing identified")

        # Analyze copy characteristics
        copy_lengths = []
        personalization_levels = []

        for data in successful_campaigns:
            if 'copy_length' in data:
                copy_lengths.append(data['copy_length'])
            if 'personalization_score' in data:
                personalization_levels.append(data['personalization_score'])

        if copy_lengths and statistics.mean(copy_lengths) < 200:
            characteristics.append("Concise copy performs better")
        elif copy_lengths and statistics.mean(copy_lengths) > 400:
            characteristics.append("Detailed copy with value props performs better")

        if personalization_levels and statistics.mean(personalization_levels) > 0.7:
            characteristics.append("High personalization correlates with success")

        return characteristics

    def _build_learning_model(self, patterns: Dict[str, Any]) -> Dict[str, Any]:
        """Build a learning model from analyzed patterns"""

        model = {
            'optimal_response_rate': patterns.get('avg_response_rate', 0.02),
            'optimal_conversion_rate': patterns.get('avg_conversion_rate', 0.005),
            'success_factors': patterns.get('common_characteristics', []),
            'recommended_strategies': [
                'high_personalization',
                'optimal_timing',
                'value_focused_copy',
                'clear_call_to_action'
            ],
            'risk_factors': [
                'low_personalization',
                'poor_timing',
                'generic_copy',
                'unclear_value_prop'
            ],
            'optimization_weights': {
                'personalization': 0.3,
                'timing': 0.2,
                'copy_quality': 0.3,
                'targeting': 0.2
            }
        }

        return model

    def apply_learned_optimizations(self, campaign_config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply learned optimizations to a new campaign"""

        # Load the latest optimization model
        model_file = self._get_latest_model()
        if not model_file:
            return {'error': 'No optimization model available'}

        try:
            with open(model_file, 'r') as f:
                model_data = json.load(f)
                optimization_model = model_data['model']
        except Exception as e:
            logger.error(f"Error loading optimization model: {e}")
            return {'error': 'Failed to load optimization model'}

        # Apply optimizations to campaign
        optimized_config = self._optimize_campaign_config(campaign_config, optimization_model)

        return {
            'status': 'optimized',
            'original_config': campaign_config,
            'optimized_config': optimized_config,
            'optimizations_applied': self._get_applied_optimizations(campaign_config, optimized_config),
            'expected_improvement': self._calculate_expected_improvement(optimization_model)
        }

    def _get_latest_model(self) -> Optional[str]:
        """Get the latest optimization model file"""

        import glob

        pattern = os.path.join(self.model_dir, "optimization_model_*.json")
        files = glob.glob(pattern)

        if not files:
            return None

        # Return most recent file
        return max(files, key=os.path.getctime)

    def _optimize_campaign_config(self, config: Dict[str, Any], model: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize campaign configuration using learned model"""

        optimized = config.copy()

        # Apply personalization optimization
        if model.get('optimization_weights', {}).get('personalization', 0) > 0.2:
            optimized['personalization_level'] = 'high'
            optimized['use_dynamic_variables'] = True

        # Apply timing optimization
        if model.get('optimization_weights', {}).get('timing', 0) > 0.2:
            optimized['send_optimization'] = True
            optimized['optimal_send_times'] = ['09:00', '14:00', '16:00']

        # Apply copy optimization
        if model.get('optimization_weights', {}).get('copy_quality', 0) > 0.2:
            optimized['copy_optimization'] = True
            optimized['ab_testing_enabled'] = True
            optimized['focus_on_benefits'] = True

        return optimized

    def _get_applied_optimizations(self, original: Dict[str, Any], optimized: Dict[str, Any]) -> List[str]:
        """Get list of optimizations applied"""

        optimizations = []

        if optimized.get('personalization_level') != original.get('personalization_level'):
            optimizations.append("Enhanced personalization")

        if optimized.get('send_optimization'):
            optimizations.append("Optimized send timing")

        if optimized.get('ab_testing_enabled'):
            optimizations.append("Enabled A/B testing")

        if optimized.get('focus_on_benefits'):
            optimizations.append("Benefit-focused copy optimization")

        return optimizations

    def _calculate_expected_improvement(self, model: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate expected improvement from optimizations"""

        base_response_rate = 0.015  # Industry average
        base_conversion_rate = 0.003

        # Calculate improvement based on model weights
        weights = model.get('optimization_weights', {})

        response_improvement = sum([
            weights.get('personalization', 0) * 0.1,
            weights.get('timing', 0) * 0.05,
            weights.get('copy_quality', 0) * 0.15,
            weights.get('targeting', 0) * 0.08
        ])

        conversion_improvement = response_improvement * 0.7  # Conversion typically 70% of response improvement

        return {
            'response_rate_improvement': round(response_improvement, 3),
            'conversion_rate_improvement': round(conversion_improvement, 3),
            'confidence_level': 'medium' if sum(weights.values()) > 0.8 else 'low'
        }

    def generate_performance_report(self, campaign_ids: Optional[List[str]] = None,
                                  days_back: int = 30) -> Dict[str, Any]:
        """Generate comprehensive performance report"""

        # Get performance analysis
        analysis = self.performance_tracker.analyze_performance_trends(campaign_ids, days_back)

        if 'error' in analysis:
            return analysis

        # Generate AI-powered insights and recommendations
        insights_prompt = f"""Analyze this campaign performance data and provide strategic insights:

PERFORMANCE ANALYSIS:
{json.dumps(analysis, indent=2)}

Provide:
1. Key performance insights
2. Strategic recommendations
3. Risk factors to monitor
4. Optimization opportunities
5. Long-term improvement strategies

Focus on actionable insights that can improve campaign performance.
"""

        try:
            ai_response = self.ai_generator._call_ai_api(insights_prompt)
            ai_insights = self._parse_ai_insights(ai_response)
        except Exception as e:
            logger.warning(f"AI insights generation failed: {e}")
            ai_insights = {
                'key_insights': ['Performance analysis completed'],
                'recommendations': ['Continue monitoring campaign metrics'],
                'risks': ['Data quality issues'],
                'opportunities': ['Further optimization possible']
            }

        return {
            'report_period': f"{days_back} days",
            'generated_at': datetime.now().isoformat(),
            'performance_analysis': analysis,
            'ai_insights': ai_insights,
            'action_items': self._generate_action_items(analysis, ai_insights),
            'next_steps': [
                'Implement top recommendations',
                'Monitor key metrics weekly',
                'A/B test optimization suggestions',
                'Review campaign targeting'
            ]
        }

    def _parse_ai_insights(self, response: str) -> Dict[str, Any]:
        """Parse AI-generated insights"""

        # Simple parsing - in real implementation would be more sophisticated
        insights = {
            'key_insights': [],
            'recommendations': [],
            'risks': [],
            'opportunities': []
        }

        lines = response.split('\n')
        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Detect sections
            if 'insight' in line.lower() or 'key finding' in line.lower():
                current_section = 'key_insights'
            elif 'recommend' in line.lower():
                current_section = 'recommendations'
            elif 'risk' in line.lower():
                current_section = 'risks'
            elif 'opportunit' in line.lower():
                current_section = 'opportunities'
            elif current_section and line.startswith(('1.', '2.', '3.', '4.', '5.', '-', '•')):
                # Add to current section
                clean_line = re.sub(r'^[\d\.\-\•]\s*', '', line)
                if current_section in insights and clean_line:
                    insights[current_section].append(clean_line)

        return insights

    def _generate_action_items(self, analysis: Dict[str, Any], ai_insights: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate prioritized action items"""

        action_items = []

        # High priority items from performance analysis
        opportunities = analysis.get('optimization_opportunities', [])
        for opp in opportunities:
            if opp.get('priority') == 'high':
                action_items.append({
                    'priority': 'high',
                    'type': opp.get('type'),
                    'description': opp.get('description'),
                    'actions': opp.get('actions', []),
                    'expected_impact': 'significant'
                })

        # AI recommendations
        recommendations = ai_insights.get('recommendations', [])
        for rec in recommendations[:3]:  # Top 3
            action_items.append({
                'priority': 'medium',
                'type': 'ai_recommended',
                'description': rec,
                'actions': [rec],
                'expected_impact': 'moderate'
            })

        return action_items

