"""
Persistent job queue implementation
"""
import json
import os
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

from .job import Job, JobStatus, ProgressInfo
from .queue import JobQueue, QueueItem


class PersistentJobQueue(JobQueue):
    """Job queue with file-based persistence"""

    def __init__(self, storage_dir: str = "./data/jobs"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache
        self._queue = []  # Priority queue
        self._jobs: Dict[str, Job] = {}  # Job storage
        self._progress_streams: Dict[str, asyncio.Queue] = {}  # Progress streams
        self._lock = asyncio.Lock()

        # Load existing jobs from disk
        self._load_jobs_from_disk()

    def _get_job_file(self, job_id: str) -> Path:
        """Get the file path for a job"""
        return self.storage_dir / f"{job_id}.json"

    def _save_job_to_disk(self, job: Job):
        """Save job to disk"""
        try:
            job_data = job.to_dict()
            job_file = self._get_job_file(job.id)
            with open(job_file, 'w') as f:
                json.dump(job_data, f, indent=2, default=str)
        except Exception as e:
            print(f"Error saving job {job.id}: {e}")

    def _load_job_from_disk(self, job_id: str) -> Optional[Job]:
        """Load job from disk"""
        try:
            job_file = self._get_job_file(job_id)
            if not job_file.exists():
                return None

            with open(job_file, 'r') as f:
                job_data = json.load(f)

            # Convert string dates back to datetime
            job_data['created_at'] = datetime.fromisoformat(job_data['created_at'])
            job_data['updated_at'] = datetime.fromisoformat(job_data['updated_at'])

            # Convert status string back to enum
            job_data['status'] = JobStatus(job_data['status'])

            # Reconstruct progress info
            if job_data.get('progress'):
                progress_data = job_data['progress']
                if progress_data.get('last_updated'):
                    progress_data['last_updated'] = datetime.fromisoformat(progress_data['last_updated'])
                if progress_data.get('estimated_completion'):
                    progress_data['estimated_completion'] = datetime.fromisoformat(progress_data['estimated_completion'])
                job_data['progress'] = ProgressInfo(**progress_data)

            return Job(**job_data)
        except Exception as e:
            print(f"Error loading job {job_id}: {e}")
            return None

    def _load_jobs_from_disk(self):
        """Load all jobs from disk"""
        try:
            if not self.storage_dir.exists():
                return

            for job_file in self.storage_dir.glob("*.json"):
                job_id = job_file.stem
                job = self._load_job_from_disk(job_id)
                if job:
                    self._jobs[job_id] = job

                    # Re-queue jobs that are still active
                    if job.status in [JobStatus.QUEUED, JobStatus.RUNNING]:
                        queue_item = QueueItem(job=job, priority=1 if job.status == JobStatus.RUNNING else 0)
                        self._queue.append(queue_item)

        except Exception as e:
            print(f"Error loading jobs from disk: {e}")

    async def enqueue_job(self, job: Job, priority: int = 0) -> str:
        """Add job to queue and persist to disk"""
        async with self._lock:
            # Store job
            self._jobs[job.id] = job

            # Save to disk
            self._save_job_to_disk(job)

            # Add to priority queue if not already running
            if job.status == JobStatus.QUEUED:
                queue_item = QueueItem(job=job, priority=priority)
                self._queue.append(queue_item)

            # Create progress stream
            self._progress_streams[job.id] = asyncio.Queue()

            return job.id

    async def dequeue_job(self) -> Optional[Job]:
        """Get next job to process"""
        async with self._lock:
            while self._queue:
                queue_item = self._queue.pop(0)  # FIFO for simplicity
                job = queue_item.job

                # Check if job is still valid
                if job.id in self._jobs and job.status == JobStatus.QUEUED:
                    # Mark as running
                    job.update_status(JobStatus.RUNNING)
                    self._save_job_to_disk(job)
                    return job
                # If job was cancelled or already processed, continue to next

            return None  # No jobs available

    async def update_job_status(self, job_id: str, status: JobStatus) -> None:
        """Update job status"""
        async with self._lock:
            job = self._jobs.get(job_id)
            if job:
                old_status = job.status
                job.update_status(status)
                self._save_job_to_disk(job)

                # Emit progress update
                if job_id in self._progress_streams:
                    try:
                        await self._progress_streams[job_id].put(job.progress)
                    except Exception:
                        pass  # Stream might be closed

    async def get_job_progress(self, job_id: str) -> Optional[ProgressInfo]:
        """Get job progress information"""
        job = self._jobs.get(job_id)
        return job.progress if job else None

    async def get_progress_stream(self, job_id: str):
        """Get async stream of progress updates"""
        if job_id not in self._progress_streams:
            # Create a queue that will immediately return None if job doesn't exist
            queue = asyncio.Queue()
            await queue.put(None)
            return queue

        return self._progress_streams[job_id]

    async def pause_job(self, job_id: str) -> None:
        """Pause a running job"""
        async with self._lock:
            job = self._jobs.get(job_id)
            if job and job.status == JobStatus.RUNNING:
                job.pause()
                self._save_job_to_disk(job)

                # Emit progress update
                if job_id in self._progress_streams:
                    try:
                        await self._progress_streams[job_id].put(job.progress)
                    except Exception:
                        pass

    async def resume_job(self, job_id: str) -> None:
        """Resume a paused job"""
        async with self._lock:
            job = self._jobs.get(job_id)
            if job and job.status == JobStatus.PAUSED:
                job.resume()
                # Re-queue the job
                await self.enqueue_job(job, priority=1)  # Higher priority for resumed jobs

                # Emit progress update
                if job_id in self._progress_streams:
                    try:
                        await self._progress_streams[job_id].put(job.progress)
                    except Exception:
                        pass

    async def cancel_job(self, job_id: str) -> None:
        """Cancel a job"""
        job = self._jobs.get(job_id)
        if job:
            job.cancel()
            self._save_job_to_disk(job)

            # Remove from queue if present
            self._queue = [item for item in self._queue if item.job.id != job_id]

            # Clean up progress stream
            if job_id in self._progress_streams:
                try:
                    await self._progress_streams[job_id].put(None)  # Signal end of stream
                except Exception:
                    pass

    async def list_jobs(self, status_filter: Optional[JobStatus] = None) -> List[Job]:
        """List jobs with optional status filter"""
        jobs = list(self._jobs.values())
        if status_filter:
            jobs = [job for job in jobs if job.status == status_filter]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        async with self._lock:
            jobs_by_status = {}
            for job in self._jobs.values():
                status = job.status.value
                jobs_by_status[status] = jobs_by_status.get(status, 0) + 1

            return {
                "total_jobs": len(self._jobs),
                "queued_jobs": len([j for j in self._queue if j.job.status == JobStatus.QUEUED]),
                "jobs_by_status": jobs_by_status,
                "active_streams": len([s for s in self._progress_streams.values() if not s.empty()]),
            }
