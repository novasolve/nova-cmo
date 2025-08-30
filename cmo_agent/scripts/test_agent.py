#!/usr/bin/env python3
"""
Test script for CMO Agent components
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.hygiene import MXCheck
from tools.personalization import RenderCopy
from core.state import RunState, JobMetadata


async def test_mx_check():
    """Test MX record validation"""
    print("🧪 Testing MX Check...")

    mx_tool = MXCheck()
    test_emails = [
        "test@gmail.com",
        "user@nonexistent-domain-12345.com",
        "contact@github.com",
    ]

    result = await mx_tool.execute(test_emails)
    print(f"✅ MX Check Result: {result.success}")
    if result.success:
        print(f"   Valid: {result.data['valid_emails']}")
        print(f"   Invalid: {result.data['invalid_emails']}")


async def test_copy_rendering():
    """Test copy personalization"""
    print("\n🧪 Testing Copy Rendering...")

    render_tool = RenderCopy()
    test_lead = {
        "name": "John Doe",
        "email": "john@example.com",
        "login": "johndoe",
        "primary_repo": "johndoe/myproject",
        "primary_language": "Python",
        "activity_90d": 15,
        "total_stars": 500,
    }

    result = await render_tool.execute(test_lead)
    print(f"✅ Copy Rendering Result: {result.success}")
    if result.success:
        print(f"   Subject: {result.data['subject']}")
        print(f"   Body preview: {result.data['body'][:100]}...")


async def test_state_management():
    """Test RunState creation and management"""
    print("\n🧪 Testing State Management...")

    # Create job metadata
    job = JobMetadata("Test campaign", "test_user")
    print(f"✅ Job Created: {job.job_id}")

    # Create initial state
    initial_state = RunState(
        **job.to_dict(),
        current_stage="initialization",
        counters={"steps": 0, "api_calls": 0},
    )

    print("✅ Initial State Created:")
    print(f"   Job ID: {initial_state['job_id']}")
    print(f"   Goal: {initial_state['goal']}")
    print(f"   Stage: {initial_state['current_stage']}")


async def main():
    """Run all tests"""
    print("🚀 CMO Agent System Test Suite")
    print("=" * 50)

    try:
        await test_state_management()
        await test_mx_check()
        await test_copy_rendering()

        print("\n" + "=" * 50)
        print("🎉 All tests completed successfully!")
        print("\nThe CMO Agent scaffolding is ready for development.")
        print("Next steps:")
        print("1. Set up API keys in .env file")
        print("2. Run: make dev-setup")
        print("3. Test full pipeline: make test-campaign")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
