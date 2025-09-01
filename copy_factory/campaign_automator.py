#!/usr/bin/env python3
"""
AI-Powered Automated Campaign Creation and Management
Automatically creates, optimizes, and manages outreach campaigns
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
import random

from .ai_copy_generator import AICopyGenerator
from .smart_icp_matcher import SmartICPMatcher
from .content_analyzer import ContentAnalyzer
from .copy_optimizer import CopyOptimizer
from .core.models import ICPProfile, ProspectData, OutreachCampaign, CopyTemplate
from .core.storage import CopyFactoryStorage

logger = logging.getLogger(__name__)


class CampaignAutomator:
    """AI-powered automated campaign creation and management"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.storage = CopyFactoryStorage()
        self.ai_generator = AICopyGenerator(api_key)
        self.icp_matcher = SmartICPMatcher(api_key)
        self.content_analyzer = ContentAnalyzer(api_key)
        self.copy_optimizer = CopyOptimizer(api_key)
        self.logger = logger

        # Campaign automation data
        self.automation_dir = "copy_factory/data/automation"
        os.makedirs(self.automation_dir, exist_ok=True)

    def create_automated_campaign(self, campaign_brief: Dict[str, Any]) -> Dict[str, Any]:
        """Create a fully automated campaign from a brief"""

        self.logger.info("🤖 Starting automated campaign creation...")

        # Step 1: Analyze campaign requirements
        requirements = self._analyze_campaign_requirements(campaign_brief)

        # Step 2: Select target ICPs
        target_icps = self._select_target_icps(requirements)

        # Step 3: Segment and select prospects
        prospect_segments = self._segment_prospects(target_icps, requirements)

        # Step 4: Generate campaign strategy
        campaign_strategy = self._generate_campaign_strategy(requirements, target_icps, prospect_segments)

        # Step 5: Create optimized copy variants
        copy_variants = self._create_optimized_copy_variants(campaign_strategy, prospect_segments)

        # Step 6: Setup campaign structure
        campaign_setup = self._setup_campaign_structure(campaign_strategy, copy_variants)

        # Step 7: Generate execution plan
        execution_plan = self._generate_execution_plan(campaign_setup)

        return {
            'campaign_id': f"auto_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'campaign_name': campaign_brief.get('name', 'AI Generated Campaign'),
            'created_at': datetime.now().isoformat(),
            'requirements': requirements,
            'target_icps': target_icps,
            'prospect_segments': prospect_segments,
            'campaign_strategy': campaign_strategy,
            'copy_variants': copy_variants,
            'campaign_setup': campaign_setup,
            'execution_plan': execution_plan,
            'automation_level': 'full'
        }

    def _analyze_campaign_requirements(self, brief: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze campaign requirements using AI"""

        prompt = f"""Analyze this campaign brief and extract structured requirements:

CAMPAIGN BRIEF:
{json.dumps(brief, indent=2)}

Extract:
1. Target audience characteristics
2. Campaign goals and KPIs
3. Content themes and messaging
4. Timeline and budget considerations
5. Success criteria

Provide analysis as JSON:
{{
  "target_audience": "description",
  "goals": ["goal1", "goal2"],
  "themes": ["theme1", "theme2"],
  "timeline": "duration",
  "budget": "considerations",
  "success_criteria": ["criteria1", "criteria2"],
  "tone": "recommended_tone",
  "channel": "recommended_channel"
}}
"""

        try:
            response = self.ai_generator._call_ai_api(prompt)

            # Parse JSON response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                return json.loads(json_str)

        except Exception as e:
            self.logger.warning(f"Campaign analysis failed: {e}")

        # Fallback requirements
        return {
            'target_audience': brief.get('target_audience', 'developers'),
            'goals': brief.get('goals', ['generate_leads', 'build_relationships']),
            'themes': brief.get('themes', ['technology', 'innovation']),
            'timeline': brief.get('timeline', '4 weeks'),
            'budget': brief.get('budget', 'standard'),
            'success_criteria': ['response_rate', 'conversion_rate'],
            'tone': brief.get('tone', 'professional'),
            'channel': brief.get('channel', 'email')
        }

    def _select_target_icps(self, requirements: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Select most relevant ICPs for the campaign"""

        all_icps = self.storage.list_icps()

        if not all_icps:
            return []

        # Score ICPs based on requirements
        icp_scores = []

        for icp in all_icps:
            score = self._score_icp_relevance(icp, requirements)
            icp_scores.append((icp, score))

        # Sort by score and select top 3
        icp_scores.sort(key=lambda x: x[1], reverse=True)
        selected_icps = icp_scores[:3]

        return [{
            'icp_id': icp.id,
            'icp_name': icp.name,
            'relevance_score': score,
            'match_reasons': self._get_icp_match_reasons(icp, requirements)
        } for icp, score in selected_icps]

    def _score_icp_relevance(self, icp: ICPProfile, requirements: Dict[str, Any]) -> float:
        """Score how relevant an ICP is for the campaign requirements"""

        score = 0.0

        # Audience match
        audience_desc = requirements.get('target_audience', '').lower()
        icp_desc = (icp.description or '').lower()

        if any(word in icp_desc for word in audience_desc.split()):
            score += 0.3

        # Theme match
        themes = requirements.get('themes', [])
        icp_text = json.dumps(icp.to_dict()).lower()

        for theme in themes:
            if theme.lower() in icp_text:
                score += 0.2

        # Goals alignment
        goals = requirements.get('goals', [])
        if 'lead_generation' in goals and icp.triggers:
            score += 0.2
        if 'relationship_building' in goals and icp.personas:
            score += 0.15

        return min(1.0, score)

    def _get_icp_match_reasons(self, icp: ICPProfile, requirements: Dict[str, Any]) -> List[str]:
        """Get reasons why this ICP matches the requirements"""

        reasons = []

        audience = requirements.get('target_audience', '').lower()
        if audience in (icp.description or '').lower():
            reasons.append(f"Matches target audience: {audience}")

        themes = requirements.get('themes', [])
        for theme in themes:
            if theme.lower() in json.dumps(icp.to_dict()).lower():
                reasons.append(f"Aligns with theme: {theme}")

        if icp.triggers:
            reasons.append("Has clear trigger events for outreach")

        return reasons

    def _segment_prospects(self, target_icps: List[Dict[str, Any]],
                          requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Segment prospects based on ICP matches and requirements"""

        # Get all prospects
        all_prospects = self.storage.list_prospects()

        if not all_prospects:
            return {'segments': [], 'total_prospects': 0}

        # ICP matching
        icp_ids = [icp['icp_id'] for icp in target_icps]
        icp_matches = self.icp_matcher.batch_match_prospects(all_prospects, self.storage.list_icps())

        # Create segments
        segments = {}

        for icp_id in icp_ids:
            segment_prospects = []
            for prospect_id, matches in icp_matches.items():
                if any(match[0] == icp_id and match[1] >= 0.7 for match in matches):
                    prospect = next((p for p in all_prospects if p.lead_id == prospect_id), None)
                    if prospect:
                        segment_prospects.append(prospect)

            if segment_prospects:
                segments[icp_id] = {
                    'prospects': segment_prospects,
                    'count': len(segment_prospects),
                    'avg_similarity': statistics.mean([max([m[1] for m in icp_matches[p.lead_id]], default=0)
                                                     for p in segment_prospects]) if segment_prospects else 0
                }

        return {
            'segments': segments,
            'total_prospects': sum(seg['count'] for seg in segments.values()),
            'segmentation_criteria': 'icp_similarity',
            'min_similarity_threshold': 0.7
        }

    def _generate_campaign_strategy(self, requirements: Dict[str, Any],
                                  target_icps: List[Dict[str, Any]],
                                  prospect_segments: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive campaign strategy"""

        prompt = f"""Generate a comprehensive campaign strategy:

REQUIREMENTS:
{json.dumps(requirements, indent=2)}

TARGET ICPS:
{[icp['icp_name'] for icp in target_icps]}

PROSPECT SEGMENTS:
{len(prospect_segments.get('segments', {}))} segments with {prospect_segments.get('total_prospects', 0)} total prospects

Generate strategy including:
1. Campaign messaging framework
2. Segmentation strategy
3. Copy optimization approach
4. Timing and sequencing
5. Success measurement

Provide as JSON:
"""

        try:
            response = self.ai_generator._call_ai_api(prompt)
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                strategy = json.loads(json_str)
            else:
                strategy = {}
        except Exception as e:
            self.logger.warning(f"Strategy generation failed: {e}")
            strategy = {}

        # Enhance with defaults
        strategy.update({
            'messaging_framework': strategy.get('messaging_framework', 'benefit-driven'),
            'segmentation_strategy': strategy.get('segmentation_strategy', 'icp-based'),
            'copy_optimization': strategy.get('copy_optimization', 'a/b_testing'),
            'timing_strategy': strategy.get('timing_strategy', 'spread_over_week'),
            'success_metrics': strategy.get('success_metrics', ['open_rate', 'response_rate', 'conversion_rate']),
            'estimated_duration': requirements.get('timeline', '4 weeks'),
            'recommended_batch_size': min(50, max(10, prospect_segments.get('total_prospects', 0) // 10))
        })

        return strategy

    def _create_optimized_copy_variants(self, campaign_strategy: Dict[str, Any],
                                       prospect_segments: Dict[str, Any]) -> Dict[str, Any]:
        """Create optimized copy variants for the campaign"""

        variants = {}
        segments = prospect_segments.get('segments', {})

        for segment_id, segment_data in segments.items():
            if segment_data['count'] == 0:
                continue

            # Get ICP for this segment
            icp = self.storage.get_icp(segment_id)
            if not icp:
                continue

            # Sample prospect for copy generation
            sample_prospect = segment_data['prospects'][0]

            # Generate base copy
            base_copy = self.ai_generator.generate_personalized_copy(
                sample_prospect, icp,
                tone=campaign_strategy.get('tone', 'professional'),
                length='medium'
            )

            # Generate A/B test variants
            ab_variants = self.copy_optimizer.generate_ab_test_variants(
                base_copy, sample_prospect, icp, num_variants=4
            )

            variants[segment_id] = {
                'base_copy': base_copy,
                'ab_variants': ab_variants,
                'sample_prospect': sample_prospect.lead_id,
                'optimization_strategy': campaign_strategy.get('copy_optimization', 'a/b_testing')
            }

        return {
            'variants_by_segment': variants,
            'total_variants': sum(len(seg.get('ab_variants', [])) for seg in variants.values()),
            'optimization_approach': campaign_strategy.get('copy_optimization', 'a/b_testing')
        }

    def _setup_campaign_structure(self, campaign_strategy: Dict[str, Any],
                                copy_variants: Dict[str, Any]) -> Dict[str, Any]:
        """Setup the campaign structure and templates"""

        # Create campaign templates
        templates = {}
        variants = copy_variants.get('variants_by_segment', {})

        for segment_id, variant_data in variants.items():
            icp = self.storage.get_icp(segment_id)
            if not icp:
                continue

            # Create template for this segment
            template = CopyTemplate(
                id=f"auto_template_{segment_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                name=f"Auto-generated template for {icp.name}",
                icp_id=segment_id,
                template_type="email",
                subject_template=variant_data['base_copy'].get('subject', ''),
                body_template=variant_data['base_copy'].get('body', ''),
                variables=['first_name', 'company', 'repo_name', 'icp_name'],
                tags=['auto_generated', 'campaign_optimized', segment_id]
            )

            self.storage.save_template(template)
            templates[segment_id] = template.id

        return {
            'templates_created': templates,
            'campaign_type': 'segmented_ab_test',
            'batch_strategy': campaign_strategy.get('timing_strategy', 'spread_over_week'),
            'total_templates': len(templates)
        }

    def _generate_execution_plan(self, campaign_setup: Dict[str, Any]) -> Dict[str, Any]:
        """Generate detailed execution plan"""

        templates = campaign_setup.get('templates_created', {})

        execution_steps = []

        # Step 1: Campaign setup
        execution_steps.append({
            'step': 1,
            'name': 'Campaign Setup',
            'description': 'Create campaign with templates and prospect lists',
            'estimated_duration': '1 day',
            'dependencies': []
        })

        # Step 2: Copy testing
        execution_steps.append({
            'step': 2,
            'name': 'A/B Testing Phase',
            'description': f'Test {len(templates)} copy variants across segments',
            'estimated_duration': '1 week',
            'dependencies': [1]
        })

        # Step 3: Optimization
        execution_steps.append({
            'step': 3,
            'name': 'Copy Optimization',
            'description': 'Analyze test results and optimize winning variants',
            'estimated_duration': '2 days',
            'dependencies': [2]
        })

        # Step 4: Full rollout
        execution_steps.append({
            'step': 4,
            'name': 'Full Campaign Rollout',
            'description': 'Execute optimized campaign to all segments',
            'estimated_duration': '2 weeks',
            'dependencies': [3]
        })

        # Step 5: Monitoring and follow-up
        execution_steps.append({
            'step': 5,
            'name': 'Monitoring & Follow-up',
            'description': 'Track performance and send follow-up sequences',
            'estimated_duration': 'ongoing',
            'dependencies': [4]
        })

        return {
            'execution_steps': execution_steps,
            'estimated_total_duration': '4 weeks',
            'milestones': ['setup_complete', 'testing_complete', 'optimization_complete', 'rollout_complete'],
            'risk_mitigation': [
                'Monitor deliverability rates',
                'A/B test all major copy changes',
                'Have backup contact channels ready',
                'Prepare response templates for common objections'
            ]
        }

    def execute_automated_campaign(self, campaign_config: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an automated campaign"""

        self.logger.info(f"🚀 Executing automated campaign: {campaign_config['campaign_name']}")

        execution_results = {
            'campaign_id': campaign_config['campaign_id'],
            'execution_started': datetime.now().isoformat(),
            'steps_completed': [],
            'performance_metrics': {},
            'issues_encountered': []
        }

        try:
            # Step 1: Create actual campaigns in storage
            campaigns_created = self._create_storage_campaigns(campaign_config)
            execution_results['campaigns_created'] = campaigns_created
            execution_results['steps_completed'].append('campaign_creation')

            # Step 2: Generate copy for all prospects
            copy_generated = self._generate_campaign_copy(campaign_config)
            execution_results['copy_generated'] = copy_generated
            execution_results['steps_completed'].append('copy_generation')

            # Step 3: Setup A/B testing framework
            ab_setup = self._setup_ab_testing(campaign_config)
            execution_results['ab_testing_setup'] = ab_setup
            execution_results['steps_completed'].append('ab_testing_setup')

            execution_results['status'] = 'execution_complete'
            execution_results['execution_completed'] = datetime.now().isoformat()

        except Exception as e:
            self.logger.error(f"Campaign execution failed: {e}")
            execution_results['status'] = 'failed'
            execution_results['error'] = str(e)
            execution_results['issues_encountered'].append(str(e))

        return execution_results

    def _create_storage_campaigns(self, campaign_config: Dict[str, Any]) -> List[str]:
        """Create actual campaign objects in storage"""

        campaigns_created = []
        segments = campaign_config.get('prospect_segments', {}).get('segments', {})

        for segment_id, segment_data in segments.items():
            campaign = OutreachCampaign(
                id=f"{campaign_config['campaign_id']}_{segment_id}",
                name=f"{campaign_config['campaign_name']} - {segment_id}",
                icp_id=segment_id,
                template_id=campaign_config['campaign_setup']['templates_created'].get(segment_id, ''),
                prospect_ids=[p.lead_id for p in segment_data['prospects']],
                status='draft'
            )

            self.storage.save_campaign(campaign)
            campaigns_created.append(campaign.id)

        return campaigns_created

    def _generate_campaign_copy(self, campaign_config: Dict[str, Any]) -> Dict[str, Any]:
        """Generate copy for the entire campaign"""

        total_copy_generated = 0
        segments_processed = 0

        segments = campaign_config.get('prospect_segments', {}).get('segments', {})

        for segment_id, segment_data in segments.items():
            prospects = segment_data['prospects']
            icp = self.storage.get_icp(segment_id)

            if not icp:
                continue

            # Generate copy for prospects in this segment
            for prospect in prospects:
                try:
                    copy = self.ai_generator.generate_personalized_copy(
                        prospect, icp,
                        tone=campaign_config.get('requirements', {}).get('tone', 'professional')
                    )
                    total_copy_generated += 1
                except Exception as e:
                    self.logger.warning(f"Failed to generate copy for {prospect.login}: {e}")

            segments_processed += 1

        return {
            'total_copy_generated': total_copy_generated,
            'segments_processed': segments_processed,
            'avg_copy_per_segment': total_copy_generated / segments_processed if segments_processed > 0 else 0
        }

    def _setup_ab_testing(self, campaign_config: Dict[str, Any]) -> Dict[str, Any]:
        """Setup A/B testing framework"""

        variants = campaign_config.get('copy_variants', {}).get('variants_by_segment', {})

        ab_tests = {}
        for segment_id, variant_data in variants.items():
            ab_variants = variant_data.get('ab_variants', [])

            if len(ab_variants) > 1:
                # Setup A/B test for this segment
                ab_tests[segment_id] = {
                    'test_id': f"ab_test_{segment_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    'variants': [v['variant_id'] for v in ab_variants],
                    'sample_size_per_variant': max(10, len(variant_data.get('prospects', [])) // len(ab_variants)),
                    'test_duration_days': 7,
                    'primary_metric': 'response_rate',
                    'secondary_metrics': ['open_rate', 'conversion_rate']
                }

        return {
            'ab_tests_created': len(ab_tests),
            'total_variants': sum(len(test.get('variants', [])) for test in ab_tests.values()),
            'estimated_test_completion': (datetime.now() + timedelta(days=7)).isoformat()
        }

    def monitor_campaign_performance(self, campaign_id: str) -> Dict[str, Any]:
        """Monitor and analyze campaign performance"""

        # Get campaign data
        campaign = self.storage.get_campaign(campaign_id)
        if not campaign:
            return {'error': f'Campaign {campaign_id} not found'}

        # Analyze performance (simplified - would integrate with actual tracking)
        performance = {
            'campaign_id': campaign_id,
            'status': campaign.status,
            'prospects_targeted': len(campaign.prospect_ids),
            'current_metrics': {
                'emails_sent': 0,  # Would come from actual sending platform
                'opens': 0,
                'responses': 0,
                'conversions': 0
            },
            'performance_trends': [],
            'recommendations': []
        }

        # Calculate rates
        sent = performance['current_metrics']['emails_sent']
        if sent > 0:
            performance['rates'] = {
                'open_rate': performance['current_metrics']['opens'] / sent,
                'response_rate': performance['current_metrics']['responses'] / sent,
                'conversion_rate': performance['current_metrics']['conversions'] / sent
            }

        return performance

    def optimize_running_campaign(self, campaign_id: str) -> Dict[str, Any]:
        """Optimize a running campaign based on performance data"""

        performance = self.monitor_campaign_performance(campaign_id)

        if 'error' in performance:
            return performance

        # Generate optimization recommendations
        recommendations = []

        rates = performance.get('rates', {})

        if rates.get('open_rate', 0) < 0.2:
            recommendations.append("Improve subject lines - current open rate is below optimal")

        if rates.get('response_rate', 0) < 0.02:
            recommendations.append("Consider copy optimization - response rate needs improvement")

        if rates.get('conversion_rate', 0) < 0.005:
            recommendations.append("Review offer/value proposition - conversion rate is low")

        return {
            'campaign_id': campaign_id,
            'current_performance': rates,
            'recommendations': recommendations,
            'optimization_actions': [
                'ab_test_subject_lines' if rates.get('open_rate', 0) < 0.2 else None,
                'optimize_copy_variants' if rates.get('response_rate', 0) < 0.02 else None,
                'review_value_prop' if rates.get('conversion_rate', 0) < 0.005 else None
            ]
        }

    def save_campaign_config(self, campaign_config: Dict[str, Any]) -> str:
        """Save campaign configuration for future reference"""

        config_file = os.path.join(self.automation_dir,
                                  f"campaign_{campaign_config['campaign_id']}.json")

        try:
            with open(config_file, 'w') as f:
                json.dump(campaign_config, f, indent=2, default=str)
            return config_file
        except Exception as e:
            self.logger.error(f"Failed to save campaign config: {e}")
            return ""

    def load_campaign_config(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """Load saved campaign configuration"""

        config_file = os.path.join(self.automation_dir, f"campaign_{campaign_id}.json")

        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Failed to load campaign config: {e}")

        return None
