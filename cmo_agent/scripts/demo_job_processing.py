#!/usr/bin/env python3
"""
Demo job processing with mock execution (no API keys required)
"""
import asyncio
import sys
from pathlib import Path
import time

# Add parent directory to path
parent_dir = str(Path(__file__).parent.parent)
sys.path.insert(0, parent_dir)

from core.job import Job, JobStatus
from core.persistent_queue import PersistentJobQueue


class MockCMOAgent:
    """Mock CMO Agent that simulates job processing"""

    def __init__(self):
        self.config = {"default_icp": {}}

    async def run_job(self, goal: str, created_by: str = "user", progress_callback=None):
        """Mock job execution with realistic progress updates"""
        print(f"🤖 Mock Agent: Starting job execution for: {goal}")

        # Simulate different stages of processing
        stages = [
            ("initialization", "Setting up job execution"),
            ("discovery", "Discovering repositories"),
            ("extraction", "Extracting contributors"),
            ("enrichment", "Enriching profiles"),
            ("validation", "Validating emails"),
            ("scoring", "Scoring leads"),
            ("personalization", "Personalizing content"),
            ("completed", "Job completed successfully")
        ]

        for i, (stage, description) in enumerate(stages):
            # Update progress
            if progress_callback:
                progress_info = {
                    "stage": stage,
                    "step": i + 1,
                    "total_steps": len(stages),
                    "current_item": description,
                    "items_processed": i,
                    "items_total": len(stages),
                    "metrics": {
                        "api_calls": (i + 1) * 5,
                        "tokens_used": (i + 1) * 100,
                        "repos_found": (i + 1) * 2,
                        "candidates_found": (i + 1) * 3,
                        "leads_enriched": i * 2,
                        "emails_to_send": i
                    }
                }
                await progress_callback(progress_info)

            print(f"📊 Stage {i+1}/{len(stages)}: {description}")
            await asyncio.sleep(0.5)  # Simulate processing time

        return {
            "success": True,
            "job_id": f"mock-{goal[:8].lower().replace(' ', '-')}",
            "final_state": {
                "goal": goal,
                "ended": True,
                "results": {
                    "repos_found": 15,
                    "leads_generated": 8,
                    "emails_validated": 6
                }
            },
            "artifacts": []
        }


async def process_job_with_mock_agent(job: Job, queue: PersistentJobQueue):
    """Process a single job with the mock agent"""
    print(f"🚀 Processing job: {job.id}")
    print(f"🎯 Goal: {job.goal}")

    # Create mock agent
    agent = MockCMOAgent()

    # Progress callback to update job
    async def progress_callback(progress_info):
        # Update job progress and persist to queue
        job.update_progress(**progress_info)
        await queue.update_job_status(job.id, job.status)  # Persist the update

    try:
        # Mark job as running and persist
        job.update_status(JobStatus.RUNNING)
        await queue.update_job_status(job.id, JobStatus.RUNNING)
        print(f"📈 Job status: {job.status.value}")

        # Execute the job
        result = await agent.run_job(job.goal, progress_callback=progress_callback)

        # Mark as completed and persist
        job.update_status(JobStatus.COMPLETED)
        await queue.update_job_status(job.id, JobStatus.COMPLETED)
        print(f"✅ Job completed: {job.id}")

        return result

    except Exception as e:
        print(f"❌ Job failed: {e}")
        job.update_status(JobStatus.FAILED)
        await queue.update_job_status(job.id, JobStatus.FAILED)
        raise


async def demo_job_execution():
    """Demo of job submission and actual processing"""
    print("🚀 CMO Agent Job Processing Demo")
    print("=" * 50)
    print("This demo shows jobs being submitted AND processed (no API keys needed)")
    print()

    # Create persistent queue
    queue = PersistentJobQueue()

    # Submit a job
    print("Step 1: Submitting job...")
    job = Job.create("Find 10 Python repos with CI and extract maintainer emails", "demo_user")
    job_id = await queue.enqueue_job(job)
    print(f"✅ Job submitted: {job_id}")
    print()

    # Process the job immediately
    print("Step 2: Processing job with mock agent...")

    # Get the job from queue
    jobs = await queue.list_jobs()
    queued_job = next((j for j in jobs if j.id == job_id), None)

    if queued_job:
        # Process the job
        result = await process_job_with_mock_agent(queued_job, queue)
        print()
        print("Step 3: Processing complete!")
        print(f"📊 Final status: {queued_job.status.value}")
        print(f"🎯 Results: {result.get('final_state', {}).get('results', {})}")
    else:
        print("❌ Could not find job in queue")

    print()
    print("Step 4: Verifying job persistence...")
    # Check that job status was saved
    saved_jobs = await queue.list_jobs()
    saved_job = next((j for j in saved_jobs if j.id == job_id), None)

    if saved_job:
        print(f"✅ Job persisted with status: {saved_job.status.value}")
        print(f"📈 Progress: {saved_job.progress.stage}")
    else:
        print("❌ Job not found after processing")

    print()
    print("🎉 Demo complete! Jobs are now being submitted AND processed.")


if __name__ == "__main__":
    asyncio.run(demo_job_execution())
