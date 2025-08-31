#!/usr/bin/env python3
"""
Simple job status checker script (no API keys required)
"""
import sys
from pathlib import Path
import argparse
import asyncio

# Add parent directory to path
parent_dir = str(Path(__file__).parent.parent)
sys.path.insert(0, parent_dir)

from core.persistent_queue import PersistentJobQueue


async def check_job_status(job_id: str):
    """Check status of a job"""
    # Create persistent queue
    queue = PersistentJobQueue()

    # Get job status
    jobs = await queue.list_jobs()
    job = next((j for j in jobs if j.id == job_id), None)

    if not job:
        print(f"❌ Job not found: {job_id}")
        print("💡 Use 'make list-jobs' to see all available jobs")
        return None

    # Get progress info
    progress = await queue.get_job_progress(job_id)

    print(f"📋 Job Status:")
    print(f"   Job ID: {job.id}")
    print(f"   Status: {job.status.value}")
    print(f"   Goal: {job.goal}")
    print(f"   Created: {job.created_at}")
    print(f"   Updated: {job.updated_at}")

    if progress:
        print(f"   Progress: {progress.stage}")
        if hasattr(progress, 'step') and progress.step is not None:
            print(f"   Step: {progress.step}")

    return job


async def list_all_jobs():
    """List all jobs"""
    # Create persistent queue
    queue = PersistentJobQueue()

    jobs = await queue.list_jobs()

    if not jobs:
        print("📋 No jobs found")
        return

    print(f"📋 All Jobs ({len(jobs)} total):")
    print("-" * 80)
    for job in jobs:
        print("15")
        print(f"   Goal: {job.goal}")
        print(f"   Created: {job.created_at}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Check CMO Agent job status")
    parser.add_argument("job_id", nargs="?", help="Job ID to check (omit to list all jobs)")

    args = parser.parse_args()

    if args.job_id:
        # Check specific job
        asyncio.run(check_job_status(args.job_id))
    else:
        # List all jobs
        asyncio.run(list_all_jobs())


if __name__ == "__main__":
    main()
