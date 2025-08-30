#!/usr/bin/env python3
"""
AI-Enhanced Command Line Interface for Copy Factory
Natural language commands and intelligent assistance
"""

import sys
import os
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import argparse
import re

from .ai_copy_generator import AICopyGenerator
from .smart_icp_matcher import SmartICPMatcher
from .content_analyzer import ContentAnalyzer
from .copy_optimizer import CopyOptimizer
from .campaign_automator import CampaignAutomator
from .core.storage import CopyFactoryStorage

logger = logging.getLogger(__name__)


class AIAssistant:
    """AI assistant for natural language command processing"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.ai_generator = AICopyGenerator(api_key)
        self.storage = CopyFactoryStorage()
        self.icp_matcher = SmartICPMatcher(api_key)
        self.content_analyzer = ContentAnalyzer(api_key)
        self.copy_optimizer = CopyOptimizer(api_key)
        self.campaign_automator = CampaignAutomator(api_key)

    def process_natural_language_command(self, command: str) -> Dict[str, Any]:
        """Process natural language command and execute appropriate actions"""

        # Analyze the command
        command_analysis = self._analyze_command(command)

        # Execute based on command type
        if command_analysis['type'] == 'create_campaign':
            return self._execute_create_campaign(command_analysis)
        elif command_analysis['type'] == 'generate_copy':
            return self._execute_generate_copy(command_analysis)
        elif command_analysis['type'] == 'analyze_prospects':
            return self._execute_analyze_prospects(command_analysis)
        elif command_analysis['type'] == 'optimize_campaign':
            return self._execute_optimize_campaign(command_analysis)
        elif command_analysis['type'] == 'get_insights':
            return self._execute_get_insights(command_analysis)
        elif command_analysis['type'] == 'setup_automation':
            return self._execute_setup_automation(command_analysis)
        else:
            return self._execute_general_assistance(command_analysis)

    def _analyze_command(self, command: str) -> Dict[str, Any]:
        """Analyze natural language command to understand intent"""

        prompt = f"""Analyze this command and determine the user's intent:

COMMAND: "{command}"

Determine:
1. Primary action (create_campaign, generate_copy, analyze_prospects, optimize_campaign, get_insights, setup_automation, general_help)
2. Target entities (campaigns, prospects, ICPs, templates)
3. Key parameters (audience, goals, tone, etc.)
4. Specific requirements or constraints

Provide analysis as JSON:
{{
  "type": "action_type",
  "intent": "brief_description",
  "entities": ["entity1", "entity2"],
  "parameters": {{"key": "value"}},
  "urgency": "high/medium/low",
  "complexity": "simple/moderate/complex"
}}
"""

        try:
            response = self.ai_generator._call_ai_api(prompt)
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                analysis = json.loads(json_str)
            else:
                analysis = self._fallback_command_analysis(command)
        except Exception as e:
            logger.warning(f"Command analysis failed: {e}")
            analysis = self._fallback_command_analysis(command)

        return analysis

    def _fallback_command_analysis(self, command: str) -> Dict[str, Any]:
        """Fallback command analysis using keyword matching"""

        command_lower = command.lower()

        # Simple keyword-based analysis
        if any(word in command_lower for word in ['create', 'build', 'setup', 'campaign']):
            action_type = 'create_campaign'
        elif any(word in command_lower for word in ['generate', 'write', 'copy', 'email']):
            action_type = 'generate_copy'
        elif any(word in command_lower for word in ['analyze', 'review', 'check', 'prospects']):
            action_type = 'analyze_prospects'
        elif any(word in command_lower for word in ['optimize', 'improve', 'better', 'test']):
            action_type = 'optimize_campaign'
        elif any(word in command_lower for word in ['insights', 'understand', 'learn', 'data']):
            action_type = 'get_insights'
        elif any(word in command_lower for word in ['automate', 'automatic', 'schedule']):
            action_type = 'setup_automation'
        else:
            action_type = 'general_help'

        return {
            'type': action_type,
            'intent': f"Execute {action_type.replace('_', ' ')}",
            'entities': [],
            'parameters': {},
            'urgency': 'medium',
            'complexity': 'moderate'
        }

    def _execute_create_campaign(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Execute campaign creation"""

        # Extract campaign parameters from analysis
        parameters = analysis.get('parameters', {})

        # Create campaign brief
        campaign_brief = {
            'name': parameters.get('name', f"AI Campaign {datetime.now().strftime('%Y%m%d')}"),
            'target_audience': parameters.get('audience', 'developers'),
            'goals': parameters.get('goals', ['generate_leads']),
            'tone': parameters.get('tone', 'professional'),
            'timeline': parameters.get('timeline', '4 weeks'),
            'channel': parameters.get('channel', 'email')
        }

        # Create automated campaign
        campaign_config = self.campaign_automator.create_automated_campaign(campaign_brief)

        # Execute the campaign
        execution_result = self.campaign_automator.execute_automated_campaign(campaign_config)

        return {
            'action': 'create_campaign',
            'campaign_config': campaign_config,
            'execution_result': execution_result,
            'summary': f"Created and executed campaign '{campaign_config['campaign_name']}' with {campaign_config.get('prospect_segments', {}).get('total_prospects', 0)} prospects"
        }

    def _execute_generate_copy(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Execute copy generation"""

        parameters = analysis.get('parameters', {})

        # Determine target prospects and ICPs
        icp_id = parameters.get('icp_id')
        prospect_ids = parameters.get('prospect_ids', [])

        if not icp_id:
            # Try to find best ICP
            icps = self.storage.list_icps()
            icp_id = icps[0].id if icps else None

        if not icp_id:
            return {'error': 'No ICP specified and none available'}

        icp = self.storage.get_icp(icp_id)
        if not icp:
            return {'error': f'ICP {icp_id} not found'}

        # Get prospects
        if not prospect_ids:
            prospects = self.storage.list_prospects(limit=5)
        else:
            prospects = [self.storage.get_prospect(pid) for pid in prospect_ids]
            prospects = [p for p in prospects if p is not None]

        if not prospects:
            return {'error': 'No prospects found'}

        # Generate copy
        generated_copy = []
        for prospect in prospects:
            copy = self.ai_generator.generate_personalized_copy(
                prospect, icp,
                tone=parameters.get('tone', 'professional'),
                length=parameters.get('length', 'medium')
            )
            generated_copy.append({
                'prospect_id': prospect.lead_id,
                'prospect_name': prospect.name,
                'subject': copy.get('subject'),
                'body_preview': copy.get('body', '')[:200] + '...'
            })

        return {
            'action': 'generate_copy',
            'icp_used': icp.name,
            'prospects_processed': len(generated_copy),
            'generated_copy': generated_copy,
            'summary': f"Generated personalized copy for {len(generated_copy)} prospects using ICP '{icp.name}'"
        }

    def _execute_analyze_prospects(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Execute prospect analysis"""

        parameters = analysis.get('parameters', {})

        # Get prospects to analyze
        limit = parameters.get('limit', 10)
        prospects = self.storage.list_prospects(limit=limit)

        if not prospects:
            return {'error': 'No prospects found'}

        # Perform analysis
        analysis_results = []
        for prospect in prospects:
            insights = self.content_analyzer.generate_personalized_insights(prospect)
            analysis_results.append({
                'prospect_id': prospect.lead_id,
                'name': prospect.name,
                'company': prospect.company,
                'insights': insights.get('personalized_angles', []),
                'pain_points': insights.get('pain_points', []),
                'interests': insights.get('interests', [])
            })

        return {
            'action': 'analyze_prospects',
            'prospects_analyzed': len(analysis_results),
            'analysis_results': analysis_results,
            'summary': f"Analyzed {len(analysis_results)} prospects for outreach insights"
        }

    def _execute_optimize_campaign(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Execute campaign optimization"""

        parameters = analysis.get('parameters', {})
        campaign_id = parameters.get('campaign_id')

        if not campaign_id:
            # Find most recent campaign
            campaigns = self.storage.list_campaigns()
            if campaigns:
                campaign_id = campaigns[0].id
            else:
                return {'error': 'No campaign specified and none found'}

        # Get campaign performance
        performance = self.campaign_automator.monitor_campaign_performance(campaign_id)

        # Generate optimization recommendations
        optimization = self.campaign_automator.optimize_running_campaign(campaign_id)

        return {
            'action': 'optimize_campaign',
            'campaign_id': campaign_id,
            'current_performance': performance.get('rates', {}),
            'recommendations': optimization.get('recommendations', []),
            'optimization_actions': optimization.get('optimization_actions', []),
            'summary': f"Analyzed campaign {campaign_id} and generated {len(optimization.get('recommendations', []))} optimization recommendations"
        }

    def _execute_get_insights(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Execute insights generation"""

        # Get overall system insights
        icp_stats = self.storage.list_icps()
        prospect_stats = self.storage.list_prospects()
        campaign_stats = self.storage.list_campaigns()

        # Generate AI-powered insights
        insights_prompt = f"""Generate insights about this lead generation system:

SYSTEM STATS:
- {len(icp_stats)} ICP profiles
- {len(prospect_stats)} total prospects
- {len([p for p in prospect_stats if p.has_email()])} prospects with emails
- {len(campaign_stats)} campaigns created

Provide 5 key insights and recommendations for improving lead generation performance.
"""

        try:
            insights_response = self.ai_generator._call_ai_api(insights_prompt)
            key_insights = self._parse_insights_response(insights_response)
        except Exception as e:
            logger.warning(f"Insights generation failed: {e}")
            key_insights = [
                "System has good email coverage for prospects",
                "Multiple ICPs allow for targeted campaigns",
                "Campaign automation can improve efficiency"
            ]

        return {
            'action': 'get_insights',
            'system_stats': {
                'icps': len(icp_stats),
                'prospects': len(prospect_stats),
                'prospects_with_emails': len([p for p in prospect_stats if p.has_email()]),
                'campaigns': len(campaign_stats)
            },
            'key_insights': key_insights,
            'recommendations': [
                "Focus on high-quality ICP-prospect matching",
                "Implement A/B testing for copy optimization",
                "Set up automated campaign workflows"
            ],
            'summary': f"Generated {len(key_insights)} key insights about the lead generation system"
        }

    def _execute_setup_automation(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Execute automation setup"""

        # Setup automated workflows
        automation_config = {
            'prospect_matching': True,
            'copy_generation': True,
            'campaign_optimization': True,
            'performance_tracking': True,
            'auto_followups': True
        }

        return {
            'action': 'setup_automation',
            'automation_config': automation_config,
            'automated_features': [
                "Automatic prospect-ICP matching",
                "AI-powered copy generation",
                "Campaign performance optimization",
                "Automated follow-up sequences"
            ],
            'summary': "Set up automated workflows for lead generation optimization"
        }

    def _execute_general_assistance(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Execute general assistance"""

        help_response = {
            'action': 'general_help',
            'capabilities': [
                "Create automated campaigns with AI optimization",
                "Generate personalized copy for prospects",
                "Analyze prospects for outreach insights",
                "Optimize campaigns with A/B testing",
                "Get AI-powered system insights",
                "Setup automated workflows"
            ],
            'examples': [
                "Create a campaign targeting Python developers",
                "Generate copy for my top 10 prospects",
                "Analyze prospects for pain points and interests",
                "Optimize my current campaign performance",
                "Show me insights about my lead generation"
            ],
            'tips': [
                "Be specific about your target audience",
                "Include goals and success criteria",
                "Mention preferred tone and style",
                "Specify timeline constraints"
            ],
            'summary': "AI Copy Factory is ready to help with intelligent lead generation"
        }

        return help_response

    def _parse_insights_response(self, response: str) -> List[str]:
        """Parse insights from AI response"""

        # Simple parsing - split by numbers or bullets
        lines = response.split('\n')
        insights = []

        for line in lines:
            line = line.strip()
            if line and len(line) > 20:  # Meaningful insights
                # Remove numbering
                line = re.sub(r'^\d+\.\s*', '', line)
                line = re.sub(r'^-\s*', '', line)
                insights.append(line)

        return insights[:5]  # Return top 5 insights

    def get_conversation_context(self) -> Dict[str, Any]:
        """Get current system context for conversation"""

        icps = self.storage.list_icps()
        prospects = self.storage.list_prospects()
        campaigns = self.storage.list_campaigns()

        return {
            'system_status': 'active',
            'icps_available': len(icps),
            'prospects_available': len(prospects),
            'campaigns_active': len(campaigns),
            'email_coverage': len([p for p in prospects if p.has_email()]) / len(prospects) if prospects else 0,
            'recent_activity': 'AI-powered campaign automation active',
            'capabilities': [
                'natural_language_commands',
                'ai_copy_generation',
                'smart_icp_matching',
                'content_analysis',
                'campaign_optimization',
                'automated_workflows'
            ]
        }


class AIEnhancedCLI:
    """AI-enhanced command line interface"""

    def __init__(self):
        self.assistant = AIAssistant()

    def run(self):
        """Run the AI-enhanced CLI"""

        print("🤖 AI Copy Factory Assistant")
        print("=" * 50)
        print("I can help you with intelligent lead generation and copy creation.")
        print("Try commands like:")
        print("• 'Create a campaign for Python developers'")
        print("• 'Generate copy for my top prospects'")
        print("• 'Analyze prospects for insights'")
        print("• 'Optimize my current campaign'")
        print("• 'Show me system insights'")
        print("\nType 'help' for more examples or 'quit' to exit.")
        print("-" * 50)

        while True:
            try:
                command = input("\n🤖 What would you like to do? ").strip()

                if not command:
                    continue

                if command.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye! AI Copy Factory will keep working in the background.")
                    break

                if command.lower() in ['help', 'h', '?']:
                    self._show_help()
                    continue

                # Process the command
                print(f"\n🔄 Processing: '{command}'")
                result = self.assistant.process_natural_language_command(command)

                # Display results
                self._display_result(result)

            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                logger.error(f"CLI error: {e}", exc_info=True)

    def _show_help(self):
        """Show help information"""

        print("\n📚 AI Copy Factory Commands")
        print("=" * 40)

        examples = [
            ("Campaign Creation", [
                "Create a campaign targeting Python developers",
                "Build an outreach campaign for startup founders",
                "Set up a campaign for data scientists"
            ]),
            ("Copy Generation", [
                "Generate personalized emails for my prospects",
                "Write copy for the top 10 leads",
                "Create outreach emails for ICP segment"
            ]),
            ("Prospect Analysis", [
                "Analyze my prospects for pain points",
                "Find insights about lead interests",
                "Review prospect engagement patterns"
            ]),
            ("Campaign Optimization", [
                "Optimize my current campaign performance",
                "Run A/B tests on copy variants",
                "Improve campaign response rates"
            ]),
            ("System Insights", [
                "Show me lead generation insights",
                "What are the top-performing ICPs",
                "Give me campaign performance summary"
            ]),
            ("Automation Setup", [
                "Set up automated campaign workflows",
                "Configure AI-powered optimizations",
                "Schedule automated follow-ups"
            ])
        ]

        for category, commands in examples:
            print(f"\n{category}:")
            for cmd in commands:
                print(f"  • {cmd}")

        print("
💡 Pro Tips:"        print("  • Be specific about your target audience"        print("  • Include goals, tone, and timeline"        print("  • Mention specific ICPs or prospect segments"        print("  • Ask for A/B testing when optimizing"

    def _display_result(self, result: Dict[str, Any]):
        """Display command execution results"""

        action = result.get('action', 'unknown')

        if action == 'create_campaign':
            self._display_campaign_result(result)
        elif action == 'generate_copy':
            self._display_copy_result(result)
        elif action == 'analyze_prospects':
            self._display_analysis_result(result)
        elif action == 'optimize_campaign':
            self._display_optimization_result(result)
        elif action == 'get_insights':
            self._display_insights_result(result)
        elif action == 'setup_automation':
            self._display_automation_result(result)
        elif action == 'general_help':
            self._display_help_result(result)
        else:
            print(f"📋 Action completed: {result.get('summary', 'Task completed')}")

        # Show any additional information
        if 'error' in result:
            print(f"❌ Error: {result['error']}")

    def _display_campaign_result(self, result: Dict[str, Any]):
        """Display campaign creation results"""

        config = result.get('campaign_config', {})
        execution = result.get('execution_result', {})

        print("🎯 Campaign Created Successfully!")
        print(f"   Name: {config.get('campaign_name', 'Unknown')}")
        print(f"   Prospects: {config.get('prospect_segments', {}).get('total_prospects', 0)}")
        print(f"   Segments: {len(config.get('prospect_segments', {}).get('segments', {}))}")
        print(f"   Status: {execution.get('status', 'Unknown')}")

        if execution.get('steps_completed'):
            print(f"   Completed Steps: {', '.join(execution['steps_completed'])}")

    def _display_copy_result(self, result: Dict[str, Any]):
        """Display copy generation results"""

        print("📧 Copy Generated Successfully!")
        print(f"   ICP Used: {result.get('icp_used', 'Unknown')}")
        print(f"   Prospects Processed: {result.get('prospects_processed', 0)}")

        copy_items = result.get('generated_copy', [])
        if copy_items:
            print("\n📋 Sample Generated Copy:")
            for i, item in enumerate(copy_items[:3]):  # Show first 3
                print(f"   {i+1}. {item.get('prospect_name', 'Unknown')}")
                print(f"      Subject: {item.get('subject', 'N/A')}")
                print(f"      Preview: {item.get('body_preview', 'N/A')}")

    def _display_analysis_result(self, result: Dict[str, Any]):
        """Display prospect analysis results"""

        print("🔍 Prospect Analysis Complete!")
        print(f"   Prospects Analyzed: {result.get('prospects_analyzed', 0)}")

        analysis_results = result.get('analysis_results', [])
        if analysis_results:
            print("\n📊 Key Findings:")
            for i, analysis in enumerate(analysis_results[:3]):  # Show first 3
                print(f"   {i+1}. {analysis.get('name', 'Unknown')}")
                if analysis.get('pain_points'):
                    print(f"      Pain Points: {', '.join(analysis['pain_points'][:2])}")
                if analysis.get('interests'):
                    print(f"      Interests: {', '.join(analysis['interests'][:2])}")

    def _display_optimization_result(self, result: Dict[str, Any]):
        """Display campaign optimization results"""

        print("⚡ Campaign Optimization Complete!")
        print(f"   Campaign: {result.get('campaign_id', 'Unknown')}")

        performance = result.get('current_performance', {})
        if performance:
            print("
📈 Current Performance:"            for metric, value in performance.items():
                print(".3f")

        recommendations = result.get('recommendations', [])
        if recommendations:
            print("
💡 Recommendations:"            for rec in recommendations:
                print(f"   • {rec}")

    def _display_insights_result(self, result: Dict[str, Any]):
        """Display system insights results"""

        stats = result.get('system_stats', {})
        print("🎯 System Insights:")
        print(f"   ICPs: {stats.get('icps', 0)}")
        print(f"   Prospects: {stats.get('prospects', 0)}")
        print(f"   Email Coverage: {stats.get('prospects_with_emails', 0)/stats.get('prospects', 1)*100:.1f}%")
        print(f"   Campaigns: {stats.get('campaigns', 0)}")

        insights = result.get('key_insights', [])
        if insights:
            print("\n🔑 Key Insights:")
            for insight in insights:
                print(f"   • {insight}")

    def _display_automation_result(self, result: Dict[str, Any]):
        """Display automation setup results"""

        print("🤖 Automation Setup Complete!")

        features = result.get('automated_features', [])
        if features:
            print("\n⚙️ Automated Features Enabled:")
            for feature in features:
                print(f"   ✅ {feature}")

    def _display_help_result(self, result: Dict[str, Any]):
        """Display help information"""

        capabilities = result.get('capabilities', [])
        examples = result.get('examples', [])

        print("🚀 AI Copy Factory Capabilities:")
        for capability in capabilities:
            print(f"   • {capability.replace('_', ' ').title()}")

        if examples:
            print("\n💡 Try these commands:")
            for example in examples[:5]:
                print(f"   • '{example}'")


def main():
    """Main entry point"""
    cli = AIEnhancedCLI()
    cli.run()


if __name__ == '__main__':
    main()
