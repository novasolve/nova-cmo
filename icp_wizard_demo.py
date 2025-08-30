#!/usr/bin/env python3
"""
ICP Wizard Demo - Showcase Enhanced Features
"""

import os
import sys
from pathlib import Path

# Add current directory and lead_intelligence to Python path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "lead_intelligence"))

from icp_wizard.icp_wizard import ICPWizard, ConversationMemory
from lead_intelligence.core.beautiful_logger import log_header


def demo_memory_system():
    """Demonstrate the conversation memory system"""
    print("\n" + "="*60)
    log_header("🧠 Conversation Memory System Demo")
    print("="*60)

    # Initialize memory system
    memory = ConversationMemory()
    print("✅ Memory system initialized")

    # Create a sample user memory
    sample_memory = {
        "conversation_count": 3,
        "successful_icps": [
            {
                "icp_id": "icp01_pypi_maintainers",
                "timestamp": "2024-01-15T10:00:00Z",
                "success_score": 0.8
            },
            {
                "icp_id": "icp02_ml_ds_maintainers",
                "timestamp": "2024-01-16T14:30:00Z",
                "success_score": 0.9
            }
        ],
        "preferred_icp_types": ["icp01_pypi_maintainers", "icp02_ml_ds_maintainers"],
        "common_industries": ["saas", "ai"],
        "technical_preferences": ["python", "machine learning"],
        "last_conversation": "2024-01-16T14:30:00Z"
    }

    # Save sample memory
    user_id = "demo_user_123"
    memory.save_user_memory(user_id, sample_memory)
    print(f"✅ Sample memory saved for user: {user_id}")

    # Load and display memory
    loaded_memory = memory.load_user_memory(user_id)
    print(f"✅ Memory loaded successfully")
    print(f"   Conversations: {loaded_memory['conversation_count']}")
    print(f"   Preferred ICPs: {', '.join(loaded_memory['preferred_icp_types'])}")
    print(f"   Industries: {', '.join(loaded_memory['common_industries'])}")
    print(f"   Tech preferences: {', '.join(loaded_memory['technical_preferences'])}")


def demo_context_awareness():
    """Demonstrate context-aware prompt enhancement"""
    print("\n" + "="*60)
    log_header("🎯 Context Awareness Demo")
    print("="*60)

    memory = ConversationMemory()
    user_id = "demo_user_123"

    # Get personalized suggestions
    suggestions = memory.get_personalized_suggestions(user_id, {})
    print("✅ Personalized suggestions generated:")
    print(f"   Success rate: {suggestions['success_rate']:.1%}")
    print(f"   Preferred ICPs: {suggestions['preferred_icps']}")
    print(f"   Conversation count: {suggestions['conversation_count']}")

    # Get context-aware prompt
    base_prompt = "Help me find the right ICP for my business."
    enhanced_prompt = memory.get_context_aware_prompt(user_id, base_prompt)

    print(f"\n✅ Context-aware prompt enhancement:")
    print(f"   Base prompt: {base_prompt}")
    print(f"   Enhanced: {'Yes' if enhanced_prompt != base_prompt else 'No enhancement needed'}")

    if enhanced_prompt != base_prompt:
        print(f"   Added context about: {', '.join(suggestions['preferred_icps'])}")


def demo_wizard_initialization():
    """Demonstrate enhanced wizard initialization"""
    print("\n" + "="*60)
    log_header("🎭 Enhanced Wizard Initialization Demo")
    print("="*60)

    try:
        # Initialize wizard with demo user
        wizard = ICPWizard(api_key="demo_key", user_identifier="demo_user_123")

        print("✅ Enhanced ICP Wizard initialized")
        print(f"   User ID: {wizard.user_identifier}")
        print(f"   Memory system: Active")
        print(f"   Analytics tracking: {'Enabled' if wizard.analytics else 'Disabled'}")

        # Show memory insights
        insights = wizard.get_memory_insights()
        print(f"\n✅ Memory insights loaded:")
        print(f"   Total conversations: {insights['total_conversations']}")
        print(f"   Successful ICPs: {insights['successful_icps']}")
        print(f"   Success rate: {insights['success_rate']:.1%}")

        if insights['preferred_icp_types']:
            print(f"   Preferred ICPs: {', '.join(insights['preferred_icp_types'])}")

    except Exception as e:
        print(f"⚠️  Wizard initialization (expected with demo key): {e}")
        print("   This is expected behavior without a real OpenAI API key")


def demo_enhanced_features():
    """Show all enhanced features working together"""
    print("\n" + "="*60)
    log_header("🚀 Enhanced ICP Wizard Features Overview")
    print("="*60)

    features = [
        "✅ Advanced Conversation Memory",
        "✅ User Preference Learning",
        "✅ Context-Aware Prompts",
        "✅ Personalized Recommendations",
        "✅ Success Metrics Tracking",
        "✅ Multi-turn Conversation Support",
        "✅ Industry & Technology Pattern Recognition",
        "✅ Persistent User Profiles",
        "✅ Conversation Analytics",
        "✅ Intelligent ICP Suggestions"
    ]

    print("🎯 Phase 2 Enhancement Features Implemented:")
    for feature in features:
        print(f"   {feature}")

    print("\n📊 Key Improvements:")
    print("   • Memory persists across sessions")
    print("   • Context-aware conversation flow")
    print("   • Learning from user preferences")
    print("   • Personalized ICP recommendations")
    print("   • Success rate tracking and analytics")
    print("   • Enhanced user experience for returning users")


def main():
    """Run the ICP Wizard demo"""
    log_header("🎯 ICP Wizard Enhanced Features Demo")

    print("🚀 Welcome to the Enhanced ICP Wizard Demo!")
    print("This demo showcases the new Phase 2 features:")
    print("   🧠 Conversation Memory & Learning")
    print("   🎯 Context Awareness")
    print("   📊 Analytics & Insights")
    print("   👥 Personalized User Experience")

    # Run demos
    demo_memory_system()
    demo_context_awareness()
    demo_wizard_initialization()
    demo_enhanced_features()

    print("\n" + "="*60)
    print("🎉 Demo Complete! The Enhanced ICP Wizard is ready for use.")
    print("="*60)
    print("💡 To try the real wizard with OpenAI API:")
    print("   export OPENAI_API_KEY=your_key_here")
    print("   make wizard")
    print("\n📚 For more information:")
    print("   python icp_wizard_cli.py --help")
    print("   python icp_wizard_cli.py --memory-stats")


if __name__ == "__main__":
    main()
