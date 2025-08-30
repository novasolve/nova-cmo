#!/usr/bin/env python3
"""
Test execution engine with persistent queue
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
parent_dir = str(Path(__file__).parent.parent)
sys.path.insert(0, parent_dir)

from scripts.run_execution import ExecutionEngine


class MockCMOAgent:
    """Mock CMO Agent for testing without API keys"""

    def __init__(self):
        self.config = {"default_icp": {}}

    async def run_job(self, goal: str, created_by: str = "user", progress_callback=None):
        """Mock job execution"""
        return {
            "success": True,
            "job_id": f"test-{goal[:8].lower().replace(' ', '-')}",
            "final_state": {"goal": goal, "ended": True},
            "artifacts": []
        }


async def test_execution_with_persistence():
    """Test that execution engine works with persistent queue"""
    print("🚀 Testing Execution Engine with Persistent Queue...")
    print("This simulates the real workflow without API keys")
    print()

    # Create execution engine with mock agent
    engine = ExecutionEngine(num_workers=1)

    # Manually set up components (skip full initialization)
    from core.job import JobManager
    from core.queue import JobController

    engine.job_manager = JobManager()
    # Note: PersistentJobQueue is already set in __init__
    engine.controller = JobController(engine.queue)
    engine.agent = MockCMOAgent()

    print("Step 1: Submit a job")
    job_goal = "Find 2k Python maintainers active 90d"
    job_id = await engine.submit_job(job_goal, created_by="test_user")
    print(f"✅ Job submitted: {job_id}")

    print("\nStep 2: Check job status immediately")
    status1 = await engine.get_job_status(job_id)
    if status1:
        print("✅ Job status found immediately!")
        print(f"   Status: {status1['status']}")
        print(f"   Goal: {status1['goal']}")
    else:
        print("❌ Job status not found immediately")
        return False

    print("\nStep 3: Simulate new script run (create new engine instance)")
    # This simulates running the script again
    engine2 = ExecutionEngine(num_workers=1)
    engine2.job_manager = JobManager()
    engine2.controller = JobController(engine2.queue)
    engine2.agent = MockCMOAgent()

    print("\nStep 4: Check job status from new instance (this was the bug)")
    status2 = await engine2.get_job_status(job_id)
    if status2:
        print("✅ SUCCESS: Job found in new instance!")
        print(f"   Job ID: {status2['job_id']}")
        print(f"   Status: {status2['status']}")
        print(f"   Goal: {status2['goal']}")
        print(f"   Created: {status2['created_at']}")
        print()
        print("🎉 BUG COMPLETELY FIXED!")
        print("Jobs now persist across script runs.")
        return True
    else:
        print("❌ FAILURE: Job not found in new instance")
        print("💥 Bug still exists")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_execution_with_persistence())
    if success:
        print("\n✅ All tests passed! The execution engine now works with persistence.")
        print("💡 You can now submit jobs and check their status across script runs.")
    else:
        print("\n❌ Test failed.")
        sys.exit(1)
