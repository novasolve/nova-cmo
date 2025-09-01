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


from enum import Enum


class JobPriority(Enum):
    """Job priority levels"""
    LOW = 1
    NORMAL = 5
    HIGH = 10
    URGENT = 15
    CRITICAL = 20


@dataclass
class QueueItem:
    """Enhanced item in the job queue with priority and scheduling"""
    job: Job
    priority: int = JobPriority.NORMAL.value  # Higher number = higher priority
    enqueued_at: datetime = None
    scheduled_at: Optional[datetime] = None  # For delayed execution
    retry_count: int = 0
    max_retries: int = 3
    last_retry_at: Optional[datetime] = None
    tags: List[str] = None  # For job categorization and filtering

    def __post_init__(self):
        if self.enqueued_at is None:
            self.enqueued_at = datetime.now()
        if self.tags is None:
            self.tags = []

    def __lt__(self, other):
        """Compare for priority queue (higher priority first, then scheduled time, then enqueue time)"""
        # First compare priority
        if self.priority != other.priority:
            return self.priority > other.priority

        # Then compare scheduled time (earlier scheduled jobs first)
        self_sched = self.scheduled_at or self.enqueued_at
        other_sched = other.scheduled_at or other.enqueued_at
        if self_sched != other_sched:
            return self_sched < other_sched

        # Finally, earlier enqueued jobs first
        return self.enqueued_at < other.enqueued_at

    @property
    def is_ready(self) -> bool:
        """Check if job is ready for execution"""
        if self.scheduled_at is None:
            return True
        return datetime.now() >= self.scheduled_at

    @property
    def can_retry(self) -> bool:
        """Check if job can be retried"""
        return self.retry_count < self.max_retries

    def mark_retry(self):
        """Mark job as retried"""
        self.retry_count += 1
        self.last_retry_at = datetime.now()
        # Increase priority slightly for retries to prevent starvation
        self.priority = min(self.priority + 1, JobPriority.CRITICAL.value)


class JobQueue(ABC):
    """Abstract base class for job queues with priority support"""

    @abstractmethod
    async def enqueue_job(self, job: Job, priority: int = JobPriority.NORMAL.value, tags: List[str] = None, scheduled_at: Optional[datetime] = None) -> str:
        """Add job to queue with priority and optional scheduling"""
        pass

    @abstractmethod
    async def dequeue_job(self, worker_tags: List[str] = None) -> Optional[Job]:
        """Get next job to process, considering worker capabilities and job scheduling"""
        pass

    @abstractmethod
    async def update_job_status(self, job_id: str, status: JobStatus) -> None:
        """Update job status"""
        pass

    @abstractmethod
    async def retry_job(self, job_id: str) -> bool:
        """Retry a failed job if retries are available"""
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
    async def schedule_job(self, job_id: str, scheduled_at: datetime) -> None:
        """Schedule a job for future execution"""
        pass

    @abstractmethod
    async def list_jobs(self, status_filter: Optional[JobStatus] = None, priority_filter: Optional[int] = None, tag_filter: Optional[str] = None) -> List[Job]:
        """List jobs with optional filters"""
        pass

    @abstractmethod
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get detailed queue statistics including priority distribution"""
        pass


class InMemoryJobQueue(JobQueue):
    """In-memory job queue implementation"""

    def __init__(self):
        self._queue = []  # Priority queue
        self._jobs: Dict[str, Job] = {}  # Job storage
        self._progress_streams: Dict[str, asyncio.Queue] = {}  # Progress streams
        self._lock = asyncio.Lock()
        # Track active SSE listeners per job for accurate stats
        self._progress_listeners: Dict[str, int] = {}

    async def enqueue_job(self, job: Job, priority: int = JobPriority.NORMAL.value, tags: List[str] = None, scheduled_at: Optional[datetime] = None) -> str:
        """Add job to queue with priority and scheduling support"""
        async with self._lock:
            # Store job
            self._jobs[job.id] = job

            # Add to priority queue if not already running
            if job.status == JobStatus.QUEUED:
                queue_item = QueueItem(
                    job=job,
                    priority=priority,
                    tags=tags or [],
                    scheduled_at=scheduled_at
                )
                heapq.heappush(self._queue, queue_item)

            # Create progress stream
            self._progress_streams[job.id] = asyncio.Queue()
            self._progress_listeners[job.id] = 0

            return job.id

    async def dequeue_job(self, worker_tags: List[str] = None) -> Optional[Job]:
        """Get next job to process, respecting scheduling and priority"""
        async with self._lock:
            # Make a copy of the queue to avoid modifying while iterating
            temp_queue = self._queue.copy()
            heapq.heapify(temp_queue)

            while temp_queue:
                queue_item = heapq.heappop(temp_queue)
                job = queue_item.job

                # Check if job is still valid
                if job.id not in self._jobs or job.status != JobStatus.QUEUED:
                    continue

                # Check if job is ready for execution (not scheduled for future)
                if not queue_item.is_ready:
                    continue

                # Check if worker can handle job (tag matching)
                if worker_tags and queue_item.tags:
                    # If job has tags and worker has tags, check for intersection
                    if not set(queue_item.tags).intersection(set(worker_tags)):
                        continue

                # Remove from actual queue and mark as running
                self._queue.remove(queue_item)
                heapq.heapify(self._queue)  # Re-heapify after removal

                job.update_status(JobStatus.RUNNING)
                return job

            return None  # No suitable jobs available

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

            # Remove from queue if present
            self._queue = [item for item in self._queue if item.job.id != job_id]

            # Clean up progress stream
            if job_id in self._progress_streams:
                try:
                    await self._progress_streams[job_id].put(None)  # Signal end of stream
                except Exception:
                    pass

    async def list_jobs(self, status_filter: Optional[JobStatus] = None, priority_filter: Optional[int] = None, tag_filter: Optional[str] = None) -> List[Job]:
        """List jobs with optional filters"""
        jobs = list(self._jobs.values())

        if status_filter:
            jobs = [job for job in jobs if job.status == status_filter]

        if priority_filter is not None:
            # Find jobs with matching priority in queue
            priority_job_ids = set()
            for item in self._queue:
                if item.priority == priority_filter:
                    priority_job_ids.add(item.job.id)
            jobs = [job for job in jobs if job.id in priority_job_ids]

        if tag_filter:
            # Find jobs with matching tags
            tagged_job_ids = set()
            for item in self._queue:
                if tag_filter in item.tags:
                    tagged_job_ids.add(item.job.id)
            jobs = [job for job in jobs if job.id in tagged_job_ids]

        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        async with self._lock:
            jobs_by_status = {}
            for job in self._jobs.values():
                status = job.status.value
                jobs_by_status[status] = jobs_by_status.get(status, 0) + 1

            # Calculate priority distribution
            priority_counts = {}
            for item in self._queue:
                priority = item.priority
                priority_counts[priority] = priority_counts.get(priority, 0) + 1

            # Calculate queue depth by priority
            priority_depths = {}
            for item in self._queue:
                priority = item.priority
                priority_depths[priority] = priority_depths.get(priority, 0) + 1

            # Active streams: number of jobs with at least one active listener
            active_streams = sum(1 for v in self._progress_listeners.values() if v > 0)

            return {
                "total_jobs": len(self._jobs),
                "queued_jobs": len(self._queue),
                "jobs_by_status": jobs_by_status,
                "jobs_by_priority": priority_counts,
                "priority_queue_depths": priority_depths,
                "active_streams": active_streams,
                "scheduled_jobs": sum(1 for item in self._queue if item.scheduled_at is not None),
            }

    async def retry_job(self, job_id: str) -> bool:
        """Retry a failed job if retries are available"""
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job or job.status != JobStatus.FAILED:
                return False

            # Find the queue item for this job
            queue_item = None
            for item in self._queue:
                if item.job.id == job_id:
                    queue_item = item
                    break

            if not queue_item:
                # Create new queue item if job failed before being queued
                queue_item = QueueItem(job=job, priority=job.metadata.get("original_priority", JobPriority.NORMAL.value))

            if not queue_item.can_retry:
                return False

            # Mark retry and re-queue
            queue_item.mark_retry()
            job.update_status(JobStatus.QUEUED)
            heapq.heappush(self._queue, queue_item)

            return True

    async def schedule_job(self, job_id: str, scheduled_at: datetime) -> None:
        """Schedule a job for future execution"""
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return

            # Find and update queue item
            for i, item in enumerate(self._queue):
                if item.job.id == job_id:
                    item.scheduled_at = scheduled_at
                    # Re-heapify to maintain priority order
                    heapq.heapify(self._queue)
                    break


class JobController:
    """Enhanced job control interface with priority and scheduling support"""

    def __init__(self, queue: JobQueue):
        self.queue = queue

    async def submit_job(self, goal: str, priority: JobPriority = JobPriority.NORMAL,
                        tags: List[str] = None, scheduled_at: Optional[datetime] = None,
                        created_by: str = "user", config: Dict[str, Any] = None) -> str:
        """Submit a new job with priority and scheduling options"""
        from .job import Job
        job = Job.create(goal, created_by, config)

        # Store original priority for retry purposes
        job.metadata["original_priority"] = priority.value

        return await self.queue.enqueue_job(job, priority.value, tags, scheduled_at)

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

    async def retry_job(self, job_id: str) -> bool:
        """Retry a failed job"""
        return await self.queue.retry_job(job_id)

    async def schedule_job(self, job_id: str, scheduled_at: datetime) -> bool:
        """Schedule a job for future execution"""
        try:
            await self.queue.schedule_job(job_id, scheduled_at)
            return True
        except Exception:
            return False

    async def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        """Get current job status"""
        job = await self._get_job_from_queue(job_id)
        return job.status if job else None

    async def get_jobs_by_priority(self, priority: JobPriority) -> List[Job]:
        """Get jobs by priority level"""
        return await self.queue.list_jobs(priority_filter=priority.value)

    async def get_jobs_by_tag(self, tag: str) -> List[Job]:
        """Get jobs by tag"""
        return await self.queue.list_jobs(tag_filter=tag)

    async def get_queue_health(self) -> Dict[str, Any]:
        """Get queue health metrics"""
        stats = await self.queue.get_queue_stats()

        # Calculate health indicators
        health_score = 100

        # Penalize high queue depth
        queue_depth = stats.get("queued_jobs", 0)
        if queue_depth > 50:
            health_score -= min(30, queue_depth // 10)

        # Penalize imbalanced priorities
        priority_depths = stats.get("priority_queue_depths", {})
        if priority_depths:
            max_priority_depth = max(priority_depths.values())
            total_depth = sum(priority_depths.values())
            if total_depth > 0 and max_priority_depth / total_depth > 0.8:
                health_score -= 20  # Starvation risk

        return {
            "health_score": max(0, health_score),
            "queue_depth": queue_depth,
            "priority_distribution": priority_depths,
            "stats": stats,
        }

    async def _get_job_from_queue(self, job_id: str) -> Optional[Job]:
        """Helper to get job from queue"""
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
