"""
Persistent job queue implementation
"""
import json
import os
import asyncio
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
import logging

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
        # Track active SSE listeners per job for accurate stats
        self._progress_listeners: Dict[str, int] = {}

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
            tmp_file = job_file.with_suffix(".tmp")
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(job_data, f, indent=2, default=str, ensure_ascii=False)
            os.replace(tmp_file, job_file)
        except Exception as e:
            logging.getLogger(__name__).error(f"Error saving job {job.id}: {e}")

    def _load_job_from_disk(self, job_id: str) -> Optional[Job]:
        """Load job from disk"""
        try:
            job_file = self._get_job_file(job_id)
            if not job_file.exists():
                return None

            with open(job_file, 'r', encoding='utf-8') as f:
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
            logging.getLogger(__name__).error(f"Error loading job {job_id}: {e}")
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

                        # Create progress stream for reloaded jobs
                        self._progress_streams[job_id] = asyncio.Queue()
                        self._progress_listeners[job_id] = 0

        except Exception as e:
            logging.getLogger(__name__).error(f"Error loading jobs from disk: {e}")

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
            self._progress_listeners[job.id] = 0

            return job.id

    async def dequeue_job(self) -> Optional[Job]:
        """Get next job to process (respects simple scheduling if set)"""
        async with self._lock:
            # Iterate to find the first ready job
            for idx, queue_item in enumerate(list(self._queue)):
                job = queue_item.job

                # Skip if scheduled in the future
                try:
                    if getattr(queue_item, "scheduled_at", None):
                        if datetime.now() < queue_item.scheduled_at:
                            continue
                except Exception:
                    pass

                # Check if job is still valid and queued
                if job.id in self._jobs and job.status == JobStatus.QUEUED:
                    # Remove from queue and mark as running
                    try:
                        self._queue.pop(idx)
                    except Exception:
                        # Fallback: remove by id filter
                        self._queue = [it for it in self._queue if it.job.id != job.id]
                    job.update_status(JobStatus.RUNNING)
                    self._save_job_to_disk(job)
                    return job

            return None  # No ready jobs available

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

                # If job reached a terminal state, close the progress stream
                if status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                    if job_id in self._progress_streams:
                        try:
                            await self._progress_streams[job_id].put(None)
                        except Exception:
                            pass

    async def get_job_progress(self, job_id: str) -> Optional[ProgressInfo]:
        """Get job progress information"""
        job = self._jobs.get(job_id)
        return job.progress if job else None

    async def get_progress_stream(self, job_id: str):
        """Get async stream of progress updates"""
        if job_id not in self._progress_streams:
            # Return an empty queue to keep SSE connection alive; server will send keep-alives
            queue = asyncio.Queue()
            return queue

        return self._progress_streams[job_id]

    def register_progress_listener(self, job_id: str):
        """Increment active listener count for a job"""
        try:
            self._progress_listeners[job_id] = self._progress_listeners.get(job_id, 0) + 1
        except Exception:
            pass

    def unregister_progress_listener(self, job_id: str):
        """Decrement active listener count for a job"""
        try:
            if job_id in self._progress_listeners and self._progress_listeners[job_id] > 0:
                self._progress_listeners[job_id] -= 1
        except Exception:
            pass

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

            active_streams = sum(1 for v in self._progress_listeners.values() if v > 0)

            return {
                "total_jobs": len(self._jobs),
                "queued_jobs": len([j for j in self._queue if j.job.status == JobStatus.QUEUED]),
                "jobs_by_status": jobs_by_status,
                "active_streams": active_streams,
            }

    async def retry_job(self, job_id: str) -> bool:
        """Retry a failed job by re-queuing it with a basic retry counter."""
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status != JobStatus.FAILED:
                return False

            # Locate existing queue item
            queue_item = None
            for item in self._queue:
                if item.job.id == job_id:
                    queue_item = item
                    break

            if not queue_item:
                # Create a minimal QueueItem if missing
                queue_item = QueueItem(job=job, priority=0)

            # Increment retry bookkeeping
            try:
                queue_item.retry_count = getattr(queue_item, "retry_count", 0) + 1
            except Exception:
                pass

            # Re-queue as QUEUED
            job.update_status(JobStatus.QUEUED)
            self._save_job_to_disk(job)
            self._queue.append(queue_item)
            return True

    async def schedule_job(self, job_id: str, scheduled_at: datetime) -> None:
        """Schedule a job for future execution (best-effort)."""
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return

            # Find queue item or create one
            queue_item = None
            for item in self._queue:
                if item.job.id == job_id:
                    queue_item = item
                    break

            if not queue_item:
                queue_item = QueueItem(job=job, priority=0)
                self._queue.append(queue_item)

            queue_item.scheduled_at = scheduled_at
            # Persist current job state (metadata remains in memory)
            self._save_job_to_disk(job)
