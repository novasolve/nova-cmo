"""
Worker system for processing CMO Agent jobs
"""
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

from .job import Job, JobStatus
from .queue import JobQueue, get_default_queue
from .monitoring import record_job_completed, record_job_failed, record_error
try:
    from ..agents.cmo_agent import CMOAgent
except ImportError:
    from agents.cmo_agent import CMOAgent

logger = logging.getLogger(__name__)


class JobWorker:
    """Individual job worker"""

    def __init__(self, worker_id: str, queue: JobQueue, agent: CMOAgent):
        self.worker_id = worker_id
        self.queue = queue
        self.agent = agent
        self.is_running = False
        self.current_job: Optional[Job] = None
        self.processed_jobs = 0
        self.failed_jobs = 0
        self.start_time = None

    async def start(self):
        """Start the worker"""
        self.is_running = True
        self.start_time = datetime.now()
        logger.info(f"Worker {self.worker_id} started")

        try:
            await self._worker_loop()
        except Exception as e:
            logger.error(f"Worker {self.worker_id} crashed: {e}")
        finally:
            self.is_running = False
            logger.info(f"Worker {self.worker_id} stopped")

    async def stop(self):
        """Stop the worker"""
        self.is_running = False
        if self.current_job:
            # Cancel current job if running
            await self.queue.cancel_job(self.current_job.id)

    async def _worker_loop(self):
        """Main worker processing loop"""
        while self.is_running:
            try:
                # Get next job from queue
                job = await self.queue.dequeue_job()

                if job:
                    self.current_job = job
                    logger.info(f"Worker {self.worker_id} processing job {job.id}: {job.goal[:50]}...")

                    try:
                        # Process the job
                        await self._process_job(job)

                        # Mark as completed
                        await self.queue.update_job_status(job.id, JobStatus.COMPLETED)
                        self.processed_jobs += 1
                        logger.info(f"Worker {self.worker_id} completed job {job.id}")

                    except Exception as e:
                        logger.error(f"Worker {self.worker_id} failed job {job.id}: {e}")
                        await self.queue.update_job_status(job.id, JobStatus.FAILED)
                        self.failed_jobs += 1

                    finally:
                        # Signal end of progress stream
                        if job and job.id in self.queue._progress_streams:
                            try:
                                await self.queue._progress_streams[job.id].put(None)  # Signal end of stream
                            except Exception as e:
                                logger.debug(f"Failed to signal end of progress stream for job {job.id}: {e}")
                        
                        self.current_job = None

                else:
                    # No jobs available, wait before checking again
                    await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Worker {self.worker_id} error in main loop: {e}")
                await asyncio.sleep(5)  # Backoff on errors

    async def _process_job(self, job: Job):
        """Process a single job"""
        start_time = datetime.now()

        try:
            # Update progress and emit to stream
            job.update_progress(stage="initializing", current_item="Setting up job execution")
            
            # Emit initial progress to stream
            if job.id in self.queue._progress_streams:
                try:
                    await self.queue._progress_streams[job.id].put(job.progress)
                except Exception as e:
                    logger.debug(f"Failed to emit initial progress for job {job.id}: {e}")

            # Create progress callback that forwards updates to the queue's progress stream
            async def progress_callback(progress_info):
                """Forward progress updates to the queue's progress stream"""
                # Normalize and update the job's progress
                if isinstance(progress_info, dict):
                    current = job.progress or None

                    provided_stage = (
                        progress_info.get("stage")
                        or progress_info.get("node")
                        or progress_info.get("event")
                    )
                    provided_stage_str = (
                        provided_stage.strip() if isinstance(provided_stage, str) else provided_stage
                    )
                    is_unknown_stage = (
                        provided_stage_str is None
                        or (isinstance(provided_stage_str, str) and provided_stage_str.strip().lower() in {"", "unknown"})
                    )

                    update_payload = {k: v for k, v in progress_info.items() if v is not None}

                    # Merge metrics dictionaries
                    if "metrics" in update_payload and isinstance(update_payload["metrics"], dict):
                        prev_metrics = (current.metrics if current and isinstance(current.metrics, dict) else {})
                        update_payload["metrics"] = {**prev_metrics, **update_payload["metrics"]}

                    if is_unknown_stage:
                        # Drop placeholder fields; keep previous stage/step
                        update_payload.pop("stage", None)
                        update_payload.pop("node", None)
                        update_payload.pop("event", None)
                        update_payload.pop("current_item", None)
                        update_payload.pop("step", None)
                    else:
                        update_payload["stage"] = provided_stage_str
                        # Only increment step on real stage transition when step not provided
                        step_provided = ("step" in progress_info and progress_info.get("step") is not None)
                        if not step_provided:
                            if current and current.stage != provided_stage_str:
                                update_payload["step"] = current.step + 1
                            else:
                                update_payload.pop("step", None)

                    job.update_progress(**update_payload)
                else:
                    job.progress = progress_info

                # Forward to queue's progress stream for SSE
                if job.id in self.queue._progress_streams:
                    try:
                        await self.queue._progress_streams[job.id].put(job.progress)
                    except Exception as e:
                        logger.debug(f"Failed to emit progress for job {job.id}: {e}")

            # Run the CMO Agent with progress callback
            result = await self.agent.run_job(job.goal, job.metadata.get('created_by', 'worker'), progress_callback)

            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()

            # Update final progress
            job.update_progress(
                stage="completed",
                items_processed=result.get('final_state', {}).get('counters', {}).get('steps', 0)
            )
            
            # Emit final progress to stream
            if job.id in self.queue._progress_streams:
                try:
                    await self.queue._progress_streams[job.id].put(job.progress)
                except Exception as e:
                    logger.debug(f"Failed to emit final progress for job {job.id}: {e}")

            # Record successful job completion
            record_job_completed(duration)
            logger.info(f"Job {job.id} completed in {duration:.1f}s")

            # Store artifacts if any
            if result.get('artifacts'):
                for artifact in result['artifacts']:
                    job.add_artifact(artifact)

            # Store final state
            if result.get('final_state'):
                job.run_state = result['final_state']

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Job processing error for {job.id}: {e}")
            job.update_progress(stage="failed", errors=[str(e)])
            
            # Emit failed progress to stream
            if job.id in self.queue._progress_streams:
                try:
                    await self.queue._progress_streams[job.id].put(job.progress)
                except Exception as e:
                    logger.debug(f"Failed to emit failed progress for job {job.id}: {e}")

            # Record job failure
            record_job_failed("job_processing")
            record_error("worker")
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Get worker statistics"""
        uptime = None
        if self.start_time:
            uptime = datetime.now() - self.start_time

        return {
            "worker_id": self.worker_id,
            "is_running": self.is_running,
            "current_job": self.current_job.id if self.current_job else None,
            "processed_jobs": self.processed_jobs,
            "failed_jobs": self.failed_jobs,
            "success_rate": self.processed_jobs / max(self.processed_jobs + self.failed_jobs, 1),
            "uptime_seconds": uptime.total_seconds() if uptime else 0,
        }


class WorkerPool:
    """Pool of job workers"""

    def __init__(self, num_workers: int = 3, queue: Optional[JobQueue] = None, agent: Optional[CMOAgent] = None):
        self.num_workers = num_workers
        self.queue = queue or get_default_queue()
        self.agent = agent  # Will be set later if not provided
        self.workers: List[JobWorker] = []
        self.tasks: List[asyncio.Task] = []
        self.is_running = False

    async def start(self, agent: Optional[CMOAgent] = None):
        """Start the worker pool"""
        if agent:
            self.agent = agent

        if not self.agent:
            raise ValueError("CMOAgent instance required to start workers")

        self.is_running = True
        logger.info(f"Starting worker pool with {self.num_workers} workers")

        # Create and start workers
        for i in range(self.num_workers):
            worker = JobWorker(f"worker-{i+1:02d}", self.queue, self.agent)
            self.workers.append(worker)

            # Start worker in background task
            task = asyncio.create_task(worker.start())
            self.tasks.append(task)

        # Start monitoring task
        monitor_task = asyncio.create_task(self._monitor_workers())
        self.tasks.append(monitor_task)

        logger.info(f"Worker pool started with {len(self.workers)} workers")

    async def stop(self):
        """Stop the worker pool"""
        if not self.is_running:
            return

        logger.info("Stopping worker pool...")
        self.is_running = False

        # Stop all workers
        for worker in self.workers:
            await worker.stop()

        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()

        # Wait for tasks to complete
        try:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error stopping worker pool: {e}")

        logger.info("Worker pool stopped")

    async def _monitor_workers(self):
        """Monitor worker health and restart failed workers"""
        while self.is_running:
            try:
                # Check worker health
                for i, worker in enumerate(self.workers):
                    if not worker.is_running and self.is_running:
                        logger.warning(f"Worker {worker.worker_id} is not running, restarting...")
                        # Create new worker
                        new_worker = JobWorker(f"worker-{i+1:02d}", self.queue, self.agent)
                        self.workers[i] = new_worker

                        # Replace task
                        if i < len(self.tasks):
                            self.tasks[i].cancel()
                            self.tasks[i] = asyncio.create_task(new_worker.start())

                # Log stats periodically
                if len(self.workers) > 0:
                    total_processed = sum(w.processed_jobs for w in self.workers)
                    total_failed = sum(w.failed_jobs for w in self.workers)

                    logger.info(f"Worker pool stats: {total_processed} processed, {total_failed} failed, "
                              f"{sum(1 for w in self.workers if w.is_running)} active workers")

                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                logger.error(f"Error in worker monitor: {e}")
                await asyncio.sleep(5)

    def get_stats(self) -> Dict[str, Any]:
        """Get worker pool statistics"""
        worker_stats = [worker.get_stats() for worker in self.workers]

        total_processed = sum(w['processed_jobs'] for w in worker_stats)
        total_failed = sum(w['failed_jobs'] for w in worker_stats)
        active_workers = sum(1 for w in worker_stats if w['is_running'])

        return {
            "pool_size": self.num_workers,
            "active_workers": active_workers,
            "total_processed": total_processed,
            "total_failed": total_failed,
            "success_rate": total_processed / max(total_processed + total_failed, 1),
            "worker_details": worker_stats,
        }

    async def scale_to(self, new_size: int):
        """Scale the worker pool to a new size"""
        if new_size == self.num_workers:
            return

        logger.info(f"Scaling worker pool from {self.num_workers} to {new_size} workers")

        if new_size > self.num_workers:
            # Add workers
            for i in range(self.num_workers, new_size):
                worker = JobWorker(f"worker-{i+1:02d}", self.queue, self.agent)
                self.workers.append(worker)

                task = asyncio.create_task(worker.start())
                self.tasks.append(task)

        else:
            # Remove workers
            for i in range(new_size, self.num_workers):
                if i < len(self.workers):
                    await self.workers[i].stop()
                    if i < len(self.tasks):
                        self.tasks[i].cancel()

            # Trim lists
            self.workers = self.workers[:new_size]
            self.tasks = self.tasks[:new_size]

        self.num_workers = new_size
        logger.info(f"Worker pool scaled to {new_size} workers")


# Convenience functions
async def start_worker_pool(num_workers: int = 3, agent: Optional[CMOAgent] = None) -> WorkerPool:
    """Start a worker pool with the given number of workers"""
    pool = WorkerPool(num_workers=num_workers)

    # Start the pool (will wait for agent if not provided)
    if agent:
        await pool.start(agent)
    else:
        # Pool will be started later when agent is provided
        pass

    return pool
