"""
Job queue system for CMO Agent
"""
import asyncio
import heapq
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass

from .job import Job, JobStatus, ProgressInfo


@dataclass
class QueueItem:
    """Item in the job queue with priority"""
    job: Job
    priority: int = 0  # Higher number = higher priority
    enqueued_at: datetime = None

    def __post_init__(self):
        if self.enqueued_at is None:
            self.enqueued_at = datetime.now()

    def __lt__(self, other):
        """Compare for priority queue (higher priority first)"""
        if self.priority != other.priority:
            return self.priority > other.priority
        # If same priority, earlier enqueued jobs first
        return self.enqueued_at < other.enqueued_at


class JobQueue(ABC):
    """Abstract base class for job queues"""

    @abstractmethod
    async def enqueue_job(self, job: Job, priority: int = 0) -> str:
        """Add job to queue"""
        pass

    @abstractmethod
    async def dequeue_job(self) -> Optional[Job]:
        """Get next job to process"""
        pass

    @abstractmethod
    async def update_job_status(self, job_id: str, status: JobStatus) -> None:
        """Update job status"""
        pass

    @abstractmethod
    async def get_job_progress(self, job_id: str) -> Optional[ProgressInfo]:
        """Get job progress information"""
        pass

    @abstractmethod
    async def get_progress_stream(self, job_id: str):
        """Get async stream of progress updates"""
        pass

    @abstractmethod
    async def pause_job(self, job_id: str) -> None:
        """Pause a running job"""
        pass

    @abstractmethod
    async def resume_job(self, job_id: str) -> None:
        """Resume a paused job"""
        pass

    @abstractmethod
    async def cancel_job(self, job_id: str) -> None:
        """Cancel a job"""
        pass

    @abstractmethod
    async def list_jobs(self, status_filter: Optional[JobStatus] = None) -> List[Job]:
        """List jobs with optional status filter"""
        pass


class InMemoryJobQueue(JobQueue):
    """In-memory job queue implementation"""

    def __init__(self):
        self._queue = []  # Priority queue
        self._jobs: Dict[str, Job] = {}  # Job storage
        self._progress_streams: Dict[str, asyncio.Queue] = {}  # Progress streams
        self._lock = asyncio.Lock()

    async def enqueue_job(self, job: Job, priority: int = 0) -> str:
        """Add job to queue"""
        async with self._lock:
            # Store job
            self._jobs[job.id] = job

            # Add to priority queue if not already running
            if job.status == JobStatus.QUEUED:
                queue_item = QueueItem(job=job, priority=priority)
                heapq.heappush(self._queue, queue_item)

            # Create progress stream
            self._progress_streams[job.id] = asyncio.Queue()

            return job.id

    async def dequeue_job(self) -> Optional[Job]:
        """Get next job to process"""
        async with self._lock:
            while self._queue:
                queue_item = heapq.heappop(self._queue)
                job = queue_item.job

                # Check if job is still valid
                if job.id in self._jobs and job.status == JobStatus.QUEUED:
                    # Mark as running
                    job.update_status(JobStatus.RUNNING)
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
        job = self._jobs.get(job_id)
        if job and job.status == JobStatus.RUNNING:
            job.pause()

    async def resume_job(self, job_id: str) -> None:
        """Resume a paused job"""
        job = self._jobs.get(job_id)
        if job and job.status == JobStatus.PAUSED:
            job.resume()
            # Re-queue the job
            await self.enqueue_job(job, priority=1)  # Higher priority for resumed jobs

    async def cancel_job(self, job_id: str) -> None:
        """Cancel a job"""
        job = self._jobs.get(job_id)
        if job:
            job.cancel()

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
                "queued_jobs": len(self._queue),
                "jobs_by_status": jobs_by_status,
                "active_streams": len([s for s in self._progress_streams.values() if not s.empty()]),
            }


class JobController:
    """Job control interface for pause/resume/cancel operations"""

    def __init__(self, queue: JobQueue):
        self.queue = queue

    async def pause_job(self, job_id: str) -> bool:
        """Pause a job if it's running"""
        job = await self._get_job_from_queue(job_id)
        if job and job.status == JobStatus.RUNNING:
            await self.queue.pause_job(job_id)
            return True
        return False

    async def resume_job(self, job_id: str) -> bool:
        """Resume a paused job"""
        job = await self._get_job_from_queue(job_id)
        if job and job.status == JobStatus.PAUSED:
            await self.queue.resume_job(job_id)
            return True
        return False

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job"""
        job = await self._get_job_from_queue(job_id)
        if job and job.status in [JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.PAUSED]:
            await self.queue.cancel_job(job_id)
            return True
        return False

    async def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        """Get current job status"""
        job = await self._get_job_from_queue(job_id)
        return job.status if job else None

    async def _get_job_from_queue(self, job_id: str) -> Optional[Job]:
        """Helper to get job from queue"""
        # This is a simplified version - in practice you'd need to implement
        # proper job retrieval in the queue interface
        jobs = await self.queue.list_jobs()
        return next((job for job in jobs if job.id == job_id), None)


# Global queue instance
_default_queue = InMemoryJobQueue()

def get_default_queue() -> JobQueue:
    """Get the default job queue instance"""
    return _default_queue

def set_default_queue(queue: JobQueue):
    """Set the default job queue instance"""
    global _default_queue
    _default_queue = queue
