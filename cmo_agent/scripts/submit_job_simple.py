#!/usr/bin/env python3
"""
Simple job submission script (no API keys required)
"""
import sys
from pathlib import Path
import argparse
import asyncio

# Add parent directory to path
parent_dir = str(Path(__file__).parent.parent)
sys.path.insert(0, parent_dir)

from core.job import Job
from core.persistent_queue import PersistentJobQueue


async def submit_job(goal: str, created_by: str = "user"):
    """Submit a job to the persistent queue"""
    # Create persistent queue
    queue = PersistentJobQueue()

    # Create and submit job
    job = Job.create(goal, created_by)
    job_id = await queue.enqueue_job(job)

    print(f"✅ Job submitted successfully!")
    print(f"   Job ID: {job_id}")
    print(f"   Goal: {goal}")
    print(f"   Created by: {created_by}")
    print()
    print("💡 To check status: make job-status JOB_ID=" + job_id)
    print("💡 To list jobs: make list-jobs")

    return job_id


def main():
    parser = argparse.ArgumentParser(description="Submit a job to the CMO Agent queue")
    parser.add_argument("goal", help="Job goal/description")
    parser.add_argument("--created-by", default="user", help="Who created the job")

    args = parser.parse_args()

    # Run async job submission
    asyncio.run(submit_job(args.goal, args.created_by))


if __name__ == "__main__":
    main()
