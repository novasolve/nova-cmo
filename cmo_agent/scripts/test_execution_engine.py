#!/usr/bin/env python3
"""
Test the execution engine job lookup fix
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
parent_dir = str(Path(__file__).parent.parent)
sys.path.insert(0, parent_dir)

from core.job import JobManager, JobStatus
from core.queue import InMemoryJobQueue, JobController
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


async def test_execution_engine_job_lookup():
    """Test the execution engine job lookup fix"""
    print("🧪 Testing Execution Engine Job Lookup Fix...")

    # Create execution engine with mock agent
    engine = ExecutionEngine(num_workers=1)

    # Manually set up components without full initialization
    engine.job_manager = JobManager()
    engine.queue = InMemoryJobQueue()
    engine.controller = JobController(engine.queue)
    engine.agent = MockCMOAgent()

    # Submit a job
    job_goal = "Find 2k Python maintainers active 90d"
    job_id = await engine.submit_job(job_goal, created_by="test_user")
    print(f"✅ Job submitted: {job_id}")

    # Test job status lookup (this was the bug)
    status = await engine.get_job_status(job_id)
    assert status is not None, f"Job status lookup failed for {job_id}"
    print(f"✅ Job status found: {status['status']}")

    # Test job listing
    jobs = await engine.list_jobs()
    assert len(jobs) > 0, "No jobs found in list"
    print(f"✅ Job list contains {len(jobs)} job(s)")

    # Test stats
    stats = await engine.get_stats_async()
    assert stats["jobs"]["total"] > 0, "No jobs in stats"
    print(f"✅ Stats show {stats['jobs']['total']} total jobs")

    print("🎉 Execution engine job lookup test passed!")


if __name__ == "__main__":
    asyncio.run(test_execution_engine_job_lookup())
