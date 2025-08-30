#!/usr/bin/env python3
"""
Demo script for CMO Agent components without API keys
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
parent_dir = str(Path(__file__).parent.parent)
sys.path.insert(0, parent_dir)

from core.state import RunState, JobMetadata, DEFAULT_CONFIG


def demo_state_management():
    """Demo the state management system"""
    print("🎯 CMO Agent State Management Demo")
    print("=" * 50)

    # Create job metadata
    job = JobMetadata("Demo campaign for Python developers", "demo_user")
    print(f"📋 Job Created:")
    print(f"   ID: {job.job_id}")
    print(f"   Goal: {job.goal}")
    print(f"   Created: {job.created_at}")
    print(f"   User: {job.created_by}")

    # Create initial state
    initial_state = RunState(
        **job.to_dict(),
        icp={
            "languages": ["python"],
            "topics": ["ci", "testing", "pytest"],
            "stars_range": "100..2000"
        },
        current_stage="initialization",
        counters={"steps": 0, "api_calls": 0, "tokens": 0},
        config=DEFAULT_CONFIG,
    )

    print(f"\n📊 Initial State Created:")
    print(f"   Job ID: {initial_state['job_id']}")
    print(f"   ICP: {initial_state['icp']}")
    print(f"   Stage: {initial_state['current_stage']}")
    print(f"   Counters: {initial_state['counters']}")

    # Simulate state progression
    print(f"\n🔄 State Progression:")

    # Stage 1: Discovery
    initial_state["current_stage"] = "discovery"
    initial_state["repos"] = [
        {
            "full_name": "pytest-dev/pytest",
            "stars": 8500,
            "topics": ["testing", "python", "ci"],
            "language": "Python"
        },
        {
            "full_name": "psf/requests",
            "stars": 48000,
            "topics": ["http", "python", "api"],
            "language": "Python"
        }
    ]
    initial_state["counters"]["steps"] = 1
    print(f"   Step 1 - Discovery: Found {len(initial_state['repos'])} repos")

    # Stage 2: Extraction
    initial_state["current_stage"] = "extraction"
    initial_state["candidates"] = [
        {
            "login": "nicoddemus",
            "from_repo": "pytest-dev/pytest",
            "signal": "Core contributor to pytest",
            "contributions": 450
        },
        {
            "login": "hugovk",
            "from_repo": "psf/requests",
            "signal": "Active maintainer",
            "contributions": 234
        }
    ]
    initial_state["counters"]["steps"] = 2
    print(f"   Step 2 - Extraction: Found {len(initial_state['candidates'])} candidates")

    # Stage 3: Enrichment
    initial_state["current_stage"] = "enrichment"
    initial_state["leads"] = [
        {
            "login": "nicoddemus",
            "name": "Bruno Oliveira",
            "email": "nicoddemus@gmail.com",
            "company": "Independent",
            "followers": 1200,
            "primary_language": "Python",
            "activity_90d": 15,
            "total_stars": 8500,
            "primary_repo": "pytest-dev/pytest"
        }
    ]
    initial_state["counters"]["steps"] = 3
    print(f"   Step 3 - Enrichment: Enriched {len(initial_state['leads'])} leads")

    # Stage 4: Personalization
    initial_state["current_stage"] = "personalization"
    initial_state["to_send"] = [
        {
            "email": "nicoddemus@gmail.com",
            "subject": "Quick fix for pytest CI flakes",
            "body": "Hi Bruno,\n\nI noticed pytest has shown recent activity with Python development...",
            "personalization": {
                "first_name": "Bruno",
                "repo": "pytest-dev/pytest",
                "language": "Python"
            }
        }
    ]
    initial_state["counters"]["steps"] = 4
    print(f"   Step 4 - Personalization: Created {len(initial_state['to_send'])} personalized emails")

    print(f"\n✅ Campaign Ready!")
    print(f"   Total steps: {initial_state['counters']['steps']}")
    print(f"   Repos found: {len(initial_state.get('repos', []))}")
    print(f"   Candidates: {len(initial_state.get('candidates', []))}")
    print(f"   Leads enriched: {len(initial_state.get('leads', []))}")
    print(f"   Emails to send: {len(initial_state.get('to_send', []))}")


def demo_config():
    """Demo the configuration system"""
    print(f"\n⚙️  Configuration Demo")
    print("=" * 30)

    print(f"📋 Default Configuration:")
    print(f"   Max Steps: {DEFAULT_CONFIG['max_steps']}")
    print(f"   Max Repos: {DEFAULT_CONFIG['max_repos']}")
    print(f"   Max People: {DEFAULT_CONFIG['max_people']}")
    print(f"   Per Inbox Daily: {DEFAULT_CONFIG['per_inbox_daily']}")
    print(f"   Languages: {DEFAULT_CONFIG['languages']}")
    print(f"   Topics: {DEFAULT_CONFIG['include_topics']}")

    print(f"\n🔧 Rate Limits:")
    for key, value in DEFAULT_CONFIG['rate_limits'].items():
        print(f"   {key}: {value}")


def main():
    """Run the demo"""
    print("🚀 CMO Agent Demo (No API Keys Required)")
    print("=" * 60)

    try:
        demo_state_management()
        demo_config()

        print(f"\n" + "=" * 60)
        print("🎉 Demo completed successfully!")
        print("\n✨ The CMO Agent scaffolding is working perfectly!")
        print("\n📝 Next Steps:")
        print("1. Set up API keys (GitHub, OpenAI, Instantly, Attio, Linear)")
        print("2. Run: python scripts/run_agent.py 'Find 2k Py maintainers'")
        print("3. Watch the full LangGraph pipeline in action!")

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
