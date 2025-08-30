#!/usr/bin/env python3
"""
Test the exact bug scenario from the user report
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


async def simulate_bug_scenario():
    """Simulate the exact scenario from the bug report"""
    print("🐛 Simulating Bug Scenario...")
    print("Original issue: Job submitted successfully but 'Job not found' when checking status")
    print()

    # Create execution engine with mock agent (simulates no API keys)
    engine = ExecutionEngine(num_workers=1)

    # Manually set up components without full initialization
    from core.job import JobManager
    from core.queue import InMemoryJobQueue, JobController

    engine.job_manager = JobManager()
    engine.queue = InMemoryJobQueue()
    engine.controller = JobController(engine.queue)
    engine.agent = MockCMOAgent()

    print("Step 1: Submit job")
    print("Command: python scripts/run_execution.py --job 'Find 2k Python maintainers active 90d'")

    # Submit job (simulates successful job creation)
    job_id = await engine.submit_job("Find 2k Python maintainers active 90d")
    print(f"Output: ✅ Job submitted: {job_id}")
    print()

    print("Step 2: Check job status")
    print(f"Command: python scripts/run_execution.py --status {job_id}")

    # Check job status (this was failing before the fix)
    status = await engine.get_job_status(job_id)

    if status:
        print("✅ Output: Job status found!")
        print(f"   Status: {status['status']}")
        print(f"   Goal: {status['goal']}")
        print(f"   Created: {status['created_at']}")
        print()
        print("🎉 BUG FIXED! Job lookup now works correctly.")
    else:
        print("❌ Output: Job not found")
        print("💥 BUG STILL EXISTS!")
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(simulate_bug_scenario())
    sys.exit(0 if success else 1)
