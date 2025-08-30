#!/usr/bin/env python3
"""
Test the job lookup fix
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
parent_dir = str(Path(__file__).parent.parent)
sys.path.insert(0, parent_dir)

from core.job import Job
from core.queue import InMemoryJobQueue


async def test_job_lookup():
    """Test that jobs can be found after enqueuing"""
    print("🧪 Testing Job Lookup Fix...")

    # Create queue
    queue = InMemoryJobQueue()

    # Create and enqueue a job
    job = Job.create("Test job lookup", "test_user")
    job_id = await queue.enqueue_job(job)
    print(f"✅ Job enqueued: {job_id}")

    # Test direct queue lookup
    jobs = await queue.list_jobs()
    found_job = next((j for j in jobs if j.id == job_id), None)
    assert found_job is not None, "Job not found in queue"
    print(f"✅ Job found in queue: {found_job.id}")

    # Test progress lookup
    progress = await queue.get_job_progress(job_id)
    assert progress is not None, "Progress not found"
    print(f"✅ Progress found: {progress.job_id}")

    # Test queue stats
    stats = await queue.get_queue_stats()
    assert stats["total_jobs"] == 1, f"Expected 1 job, got {stats['total_jobs']}"
    print(f"✅ Queue stats correct: {stats}")

    print("🎉 Job lookup test passed!")


if __name__ == "__main__":
    asyncio.run(test_job_lookup())
