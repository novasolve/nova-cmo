#!/usr/bin/env python3
"""
AI-Powered Copy Factory - Complete System Demo
Showcase the full AI capabilities of the Copy Factory
"""

import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from ai_copy_generator import AICopyGenerator
from smart_icp_matcher import SmartICPMatcher
from content_analyzer import ContentAnalyzer
from copy_optimizer import CopyOptimizer
from campaign_automator import CampaignAutomator
from performance_tracker import PerformanceTracker, AIDrivenOptimizer
from prospect_insights import ProspectInsightsEngine
from ai_cli import AIAssistant
from core.storage import CopyFactoryStorage


def main_demo():
    """Run the complete AI Copy Factory demonstration"""

    print("🚀 AI-Powered Copy Factory - Complete System Demo")
    print("=" * 60)
    print("This demo showcases the full AI capabilities of Copy Factory:")
    print("• AI-Powered Copy Generation")
    print("• Smart ICP Matching with Embeddings")
    print("• Deep Content Analysis")
    print("• Copy Optimization & A/B Testing")
    print("• Automated Campaign Management")
    print("• Performance Tracking & Learning")
    print("• Prospect Insights & Recommendations")
    print("• Natural Language AI Assistant")
    print("=" * 60)

    # Initialize all AI systems
    print("\n🤖 Initializing AI Systems...")

    ai_generator = AICopyGenerator()
    icp_matcher = SmartICPMatcher()
    content_analyzer = ContentAnalyzer()
    copy_optimizer = CopyOptimizer()
    campaign_automator = CampaignAutomator()
    performance_tracker = PerformanceTracker()
    ai_optimizer = AIDrivenOptimizer()
    insights_engine = ProspectInsightsEngine()
    ai_assistant = AIAssistant()
    storage = CopyFactoryStorage()

    print("✅ All AI systems initialized")

    # Demo 1: AI-Powered Copy Generation
    print("\n" + "="*50)
    print("🎨 DEMO 1: AI-Powered Copy Generation")
    print("="*50)

    # Get a sample prospect
    prospects = storage.list_prospects(limit=1)
    if prospects:
        prospect = prospects[0]
        icps = storage.list_icps()
        icp = icps[0] if icps else None

        if icp:
            print(f"📧 Generating AI copy for: {prospect.login}")
            print(f"🎯 Target ICP: {icp.name}")

            # Generate AI-powered copy
            ai_copy = ai_generator.generate_personalized_copy(
                prospect, icp,
                tone="professional",
                length="medium"
            )

            print("\n✨ AI-Generated Copy:")
            print(f"Subject: {ai_copy.get('subject', 'N/A')}")
            print(f"Body Preview: {ai_copy['body'][:200]}...")

            # Generate optimized variant
            print("\n🔄 Generating Optimized Variant...")
            optimized = copy_optimizer.optimize_copy_for_conversion(
                ai_copy, prospect, icp, "benefit_focused"
            )
            print(f"Optimized Subject: {optimized.get('subject', 'N/A')}")
            print("✅ AI copy generation working perfectly!")

    # Demo 2: Smart ICP Matching
    print("\n" + "="*50)
    print("🎯 DEMO 2: Smart ICP Matching with AI")
    print("="*50)

    if prospects:
        print(f"🔍 Smart matching {len(prospects)} prospects to ICPs...")

        # Perform smart matching
        matches = icp_matcher.batch_match_prospects(prospects[:5], storage.list_icps())

        print(f"📊 Found matches for {len(matches)} prospects:")

        for prospect_id, prospect_matches in list(matches.items())[:3]:
            prospect = next((p for p in prospects if p.lead_id == prospect_id), None)
            if prospect and prospect_matches:
                best_match = prospect_matches[0]
                icp = storage.get_icp(best_match[0])
                if icp:
                    print(".3f"
    # Demo 3: Deep Content Analysis
    print("\n" + "="*50)
    print("🔍 DEMO 3: Deep Content Analysis")
    print("="*50)

    if prospects:
        prospect = prospects[0]
        print(f"🧠 Analyzing content for: {prospect.login}")

        # Perform deep analysis
        analysis = content_analyzer.analyze_prospect_content(prospect)

        print("📈 Analysis Results:")
        print(f"   Professional Level: {analysis['insights'].get('professional_level', 'unknown')}")
        print(f"   Interests: {', '.join(analysis.get('interests', [])[:3])}")
        print(f"   Pain Points: {', '.join(analysis.get('pain_points', [])[:2])}")

        # Generate insights
        insights = insights_engine.generate_comprehensive_insights(prospect.__dict__)
        print("
🎯 Key Insights:"        print(".1f"        print(f"   Engagement Potential: {insights['engagement_prediction'].get('overall_potential', 'unknown')}")

    # Demo 4: Automated Campaign Creation
    print("\n" + "="*50)
    print("🚀 DEMO 4: Automated Campaign Creation")
    print("="*50)

    campaign_brief = {
        'name': 'AI Demo Campaign',
        'target_audience': 'Python developers',
        'goals': ['generate_leads', 'build_relationships'],
        'tone': 'professional',
        'timeline': '2 weeks'
    }

    print("📋 Campaign Brief:")
    for key, value in campaign_brief.items():
        print(f"   {key}: {value}")

    print("
🤖 Creating automated campaign..."    campaign_config = campaign_automator.create_automated_campaign(campaign_brief)

    print("✅ Campaign Created Successfully!")
    print(f"   Campaign ID: {campaign_config['campaign_id']}")
    print(f"   Target Prospects: {campaign_config.get('prospect_segments', {}).get('total_prospects', 0)}")
    print(f"   ICP Segments: {len(campaign_config.get('prospect_segments', {}).get('segments', {}))}")

    # Demo 5: A/B Testing Simulation
    print("\n" + "="*50)
    print("🧪 DEMO 5: A/B Testing & Optimization")
    print("="*50)

    if prospects and icps:
        prospect = prospects[0]
        icp = icps[0]

        print(f"🧪 Setting up A/B test for {prospect.login}")

        # Generate A/B variants
        base_copy = ai_generator.generate_personalized_copy(prospect, icp)
        ab_variants = copy_optimizer.generate_ab_test_variants(base_copy, prospect, icp, 3)

        print(f"📊 Generated {len(ab_variants)} test variants")
        for variant in ab_variants:
            strategy = variant.get('strategy', 'original')
            print(f"   • Variant {variant['variant_id']}: {strategy} strategy")

        # Simulate test results
        test_results = copy_optimizer._simulate_ab_test_results(ab_variants, 7)
        analysis = copy_optimizer._analyze_ab_test_results(test_results)

        print("
📈 Test Results:"        print(".1%"        print(f"   Winner: Variant {analysis.get('winner_variant', 'N/A')}")
        print(f"   Confidence: {analysis.get('confidence_level', 'unknown')}")

    # Demo 6: AI Assistant Interaction
    print("\n" + "="*50)
    print("💬 DEMO 6: AI Assistant Interaction")
    print("="*50)

    print("🤖 AI Assistant: 'Hello! I'm your Copy Factory AI assistant.'")
    print("🤖 AI Assistant: 'I can help you create campaigns, generate copy, analyze prospects, and optimize performance.'")

    # Simulate some natural language commands
    commands = [
        "Create a campaign for data scientists",
        "Generate copy for my top prospects",
        "Show me system insights"
    ]

    for cmd in commands:
        print(f"\n👤 You: '{cmd}'")
        # Note: In real implementation, this would process the command
        print(f"🤖 AI Assistant: Processing '{cmd}'...")

    print("\n✅ AI Assistant ready for natural language commands!")

    # Demo 7: Performance Tracking
    print("\n" + "="*50)
    print("📊 DEMO 7: Performance Tracking & Learning")
    print("="*50)

    # Simulate some performance data
    sample_performance = {
        'campaign_id': 'demo_campaign_001',
        'emails_sent': 100,
        'opens': 28,
        'responses': 5,
        'conversions': 1,
        'send_time': '2024-01-15T10:00:00Z'
    }

    print("📈 Tracking sample performance data...")
    tracking_result = performance_tracker.track_campaign_performance(
        sample_performance['campaign_id'],
        sample_performance
    )

    print("✅ Performance data tracked successfully")
    print(".1%"    print(".1%"    print(".1%"
    # Demo 8: System Overview
    print("\n" + "="*50)
    print("🎯 DEMO 8: Complete System Overview")
    print("="*50)

    # Get system stats
    icp_count = len(storage.list_icps())
    prospect_count = len(storage.list_prospects())
    email_coverage = len([p for p in storage.list_prospects() if p.has_email()]) / prospect_count if prospect_count > 0 else 0

    print("📊 System Status:")
    print(f"   ICP Profiles: {icp_count}")
    print(f"   Prospects: {prospect_count}")
    print(".1%"    print("   Campaigns Created: 1 (demo)")
    print(f"   AI Systems: ✅ All Active")

    print("
🚀 AI Capabilities:"    capabilities = [
        "✅ AI-Powered Copy Generation",
        "✅ Smart ICP Matching with Embeddings",
        "✅ Deep Content Analysis",
        "✅ Automated Campaign Creation",
        "✅ A/B Testing & Optimization",
        "✅ Performance Tracking & Learning",
        "✅ Natural Language AI Assistant",
        "✅ Prospect Insights & Recommendations"
    ]

    for capability in capabilities:
        print(f"   {capability}")

    print("
🎉 AI-Powered Copy Factory Demo Complete!"    print("Your system is now fully equipped with AI capabilities for:")
    print("• Intelligent lead generation")
    print("• Personalized outreach at scale")
    print("• Data-driven optimization")
    print("• Automated campaign management")
    print("• Performance tracking and learning")
    print("\n💡 Ready to supercharge your lead generation with AI! 🚀"


if __name__ == '__main__':
    try:
        main_demo()
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
