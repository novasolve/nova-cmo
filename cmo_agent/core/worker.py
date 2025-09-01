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
    try:
        from agents.cmo_agent import CMOAgent
    except ImportError:
        # Use absolute import to avoid relative import issues
        from cmo_agent.agents.cmo_agent import CMOAgent

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

        # Crash recovery and health monitoring
        self.heartbeat_interval = 30  # seconds
        self.last_heartbeat = datetime.now()
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.worker_registry = {}  # Track other workers for crash detection
        self.crash_recovery_enabled = True

    async def start(self):
        """Start the worker"""
        self.is_running = True
        self.start_time = datetime.now()
        self.last_heartbeat = datetime.now()
        logger.info(f"Worker {self.worker_id} started")

        # Start heartbeat task
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        # Perform crash recovery check
        if self.crash_recovery_enabled:
            await self._perform_crash_recovery()

        try:
            await self._worker_loop()
        except Exception as e:
            logger.error(f"Worker {self.worker_id} crashed: {e}")
            await self._handle_worker_crash()
        finally:
            self.is_running = False
            if self.heartbeat_task and not self.heartbeat_task.done():
                self.heartbeat_task.cancel()
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
                        result = await self._process_job(job)

                        # Decide final job status based on agent result
                        if result and result.get('paused'):
                            # Leave status as RUNNING/PAUSED management handled elsewhere
                            logger.info(f"Worker {self.worker_id} paused job {job.id}")
                        else:
                            if result and result.get('success') is False:
                                await self.queue.update_job_status(job.id, JobStatus.FAILED)
                                self.failed_jobs += 1
                                logger.info(f"Worker {self.worker_id} marked job {job.id} as FAILED")
                            else:
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
        """Process a single job with pause/resume support"""
        start_time = datetime.now()

        try:
            # Removed synthetic smoke paths: all jobs run the full pipeline

            # Assign this worker to the job for crash recovery
            job.metadata["assigned_worker"] = self.worker_id
            job.metadata["assigned_at"] = datetime.now().isoformat()

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
                logger.info(f"🔄 Progress callback called for job {job.id}: {progress_info}")

                # Normalize and update the job's progress
                if isinstance(progress_info, dict):
                    current = job.progress or None
                    # Choose a meaningful stage fallback
                    normalized_stage = (
                        progress_info.get("stage")
                        or progress_info.get("node")
                        or progress_info.get("event")
                        or (current.stage if current else None)
                        or "working"
                    )
                    # Auto-increment step when not provided
                    try:
                        current_step = int(progress_info.get("step")) if progress_info.get("step") is not None else None
                    except Exception:
                        current_step = None
                    normalized_step = (
                        current_step
                        if current_step is not None
                        else ((current.step + 1) if current else 0)
                    )

                    # Build update payload without overwriting with None
                    update_payload = {k: v for k, v in progress_info.items() if v is not None}
                    update_payload["stage"] = normalized_stage
                    update_payload["step"] = normalized_step

                    job.update_progress(**update_payload)
                    logger.info(f"✅ Updated job progress: stage={normalized_stage}, step={normalized_step}")
                else:
                    job.progress = progress_info
                    logger.info(f"✅ Set job progress object: {progress_info}")

                # Forward to queue's progress stream for SSE
                if job.id in self.queue._progress_streams:
                    try:
                        await self.queue._progress_streams[job.id].put(job.progress)
                        logger.info(f"📡 Emitted progress to stream for job {job.id}")
                    except Exception as e:
                        logger.error(f"❌ Failed to emit progress for job {job.id}: {e}")
                else:
                    logger.warning(f"⚠️ No progress stream found for job {job.id}")
                    logger.info(f"Available streams: {list(self.queue._progress_streams.keys())}")

            # Run the CMO Agent with progress callback
            result = await self.agent.run_job(job.goal, job.metadata.get('created_by', 'worker'), progress_callback)

            # On normal completion, ensure a final summary message is emitted to the stream
            try:
                summary = None
                final_state = result.get('final_state') if isinstance(result, dict) else None
                if isinstance(final_state, dict):
                    # Prefer agent-provided summary if present
                    report = final_state.get('report') or {}
                    summary = (report.get('summary') or {}).get('text') or report.get('summary')
                    # Fallback: synthesize a small summary
                    if not summary:
                        steps = (final_state.get('counters') or {}).get('steps', 0)
                        leads = len(final_state.get('leads') or [])
                        repos = len(final_state.get('repos') or [])
                        summary = f"Job {job.id} completed. steps={steps}, repos={repos}, leads={leads}."

                if summary:
                    # Emit as a final progress payload so UI can render a message
                    from .job import ProgressInfo
                    job.update_progress(stage="completed", message=summary)
                    if job.id in self.queue._progress_streams:
                        try:
                            await self.queue._progress_streams[job.id].put(job.progress)
                        except Exception as e:
                            logger.debug(f"Failed to emit final summary for job {job.id}: {e}")
            except Exception:
                # Non-fatal if summary emission fails
                pass

            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()

            # Check if job was paused
            if result.get('paused'):
                # Job was paused, don't mark as completed but finalize partial results
                job.update_progress(stage="paused", current_item="Job paused by user request")

                # Emit paused progress to stream
                if job.id in self.queue._progress_streams:
                    try:
                        await self.queue._progress_streams[job.id].put(job.progress)
                    except Exception as e:
                        logger.debug(f"Failed to emit paused progress for job {job.id}: {e}")

                # Finalize partial results for paused job
                if hasattr(self.agent, '_finalize_job'):
                    try:
                        finalization_result = await self.agent._finalize_job(job.id, result.get('final_state'), "paused")
                        if finalization_result:
                            job.artifacts.extend(finalization_result.get("artifacts", []))
                    except Exception as e:
                        logger.warning(f"Failed to finalize paused job {job.id}: {e}")

                return result

            # Update final progress and metrics based on success/failure
            final_state = result.get('final_state', {}) if result else {}
            steps_done = final_state.get('counters', {}).get('steps', 0)
            if result and result.get('success') is False:
                job.update_progress(stage="failed", items_processed=steps_done)
                record_job_failed("agent")
                logger.info(f"Job {job.id} failed in {duration:.1f}s")
            else:
                job.update_progress(stage="completed", items_processed=steps_done)
                record_job_completed(duration)
                logger.info(f"Job {job.id} completed in {duration:.1f}s")

            # Emit final progress to stream
            if job.id in self.queue._progress_streams:
                try:
                    await self.queue._progress_streams[job.id].put(job.progress)
                except Exception as e:
                    logger.debug(f"Failed to emit final progress for job {job.id}: {e}")

            # Store artifacts if any
            if result.get('artifacts'):
                for artifact in result['artifacts']:
                    job.add_artifact(artifact)

            # Store final state
            if result.get('final_state'):
                job.run_state = result['final_state']

            return result

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"Job processing error for {job.id}: {e}")
            job.update_progress(stage="failed", errors=[str(e)])

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
            "last_heartbeat": self.last_heartbeat.isoformat(),
        }

    async def _heartbeat_loop(self):
        """Send periodic heartbeats to indicate worker health"""
        while self.is_running:
            try:
                self.last_heartbeat = datetime.now()
                await self._send_heartbeat()
                await asyncio.sleep(self.heartbeat_interval)
            except Exception as e:
                logger.error(f"Heartbeat error for worker {self.worker_id}: {e}")
                await asyncio.sleep(self.heartbeat_interval)

    async def _send_heartbeat(self):
        """Send heartbeat signal - could be to a database or shared storage"""
        # For now, just log it. In production, this would update a shared registry
        logger.debug(f"Worker {self.worker_id} heartbeat at {self.last_heartbeat}")

        # Store heartbeat in a simple registry (in production, use Redis/DB)
        heartbeat_data = {
            "worker_id": self.worker_id,
            "timestamp": self.last_heartbeat.isoformat(),
            "current_job": self.current_job.id if self.current_job else None,
            "is_running": self.is_running,
            "processed_jobs": self.processed_jobs,
            "failed_jobs": self.failed_jobs,
        }

        # Store in worker registry for crash detection
        self.worker_registry[self.worker_id] = heartbeat_data

    async def _perform_crash_recovery(self):
        """Check for crashed workers and recover their jobs"""
        logger.info(f"Worker {self.worker_id} performing crash recovery check")

        try:
            # Get all jobs that are marked as running
            jobs = await self.queue.list_jobs()
            running_jobs = [job for job in jobs if job.status == JobStatus.RUNNING]

            recovered_count = 0
            for job in running_jobs:
                # Check if the job's worker is still alive
                if await self._is_worker_crashed(job):
                    logger.info(f"Recovering job {job.id} from crashed worker")
                    # Reset job status to queued for reassignment
                    job.update_status(JobStatus.QUEUED)
                    await self.queue.update_job_status(job.id, JobStatus.QUEUED)
                    recovered_count += 1

            if recovered_count > 0:
                logger.info(f"Worker {self.worker_id} recovered {recovered_count} jobs from crashed workers")

        except Exception as e:
            logger.error(f"Crash recovery failed for worker {self.worker_id}: {e}")

    async def _is_worker_crashed(self, job: Job) -> bool:
        """Determine if a worker has crashed based on job metadata and heartbeat data"""
        try:
            # Check job metadata for worker information
            worker_id = job.metadata.get("assigned_worker")
            if not worker_id:
                # Job doesn't have worker assignment info, assume it's from a crashed worker
                return True

            # Check if worker is in registry and has recent heartbeat
            if worker_id not in self.worker_registry:
                return True

            worker_data = self.worker_registry[worker_id]
            last_heartbeat = datetime.fromisoformat(worker_data["timestamp"])
            time_since_heartbeat = datetime.now() - last_heartbeat

            # Consider worker crashed if no heartbeat for more than 2x heartbeat interval
            max_age = timedelta(seconds=self.heartbeat_interval * 2)
            return time_since_heartbeat > max_age

        except Exception as e:
            logger.error(f"Error checking if worker crashed for job {job.id}: {e}")
            return True  # Assume crashed if we can't determine

    async def _handle_worker_crash(self):
        """Handle this worker's crash - mark current job for recovery"""
        try:
            if self.current_job:
                logger.warning(f"Worker {self.worker_id} crashed while processing job {self.current_job.id}")
                # The job will be recovered by another worker during crash recovery
                # Don't change status here - let recovery process handle it
        except Exception as e:
            logger.error(f"Error handling crash for worker {self.worker_id}: {e}")

    async def check_worker_health(self, worker_id: str) -> bool:
        """Check if a specific worker is healthy"""
        if worker_id not in self.worker_registry:
            return False

        worker_data = self.worker_registry[worker_id]
        last_heartbeat = datetime.fromisoformat(worker_data["timestamp"])
        time_since_heartbeat = datetime.now() - last_heartbeat

        # Worker is healthy if heartbeat is recent
        max_age = timedelta(seconds=self.heartbeat_interval * 1.5)
        return time_since_heartbeat <= max_age


class WorkerPool:
    """Pool of job workers with crash recovery"""

    def __init__(self, num_workers: int = 3, queue: Optional[JobQueue] = None, agent: Optional[CMOAgent] = None):
        self.num_workers = num_workers
        self.queue = queue or get_default_queue()
        self.agent = agent  # Will be set later if not provided
        self.workers: List[JobWorker] = []
        self.tasks: List[asyncio.Task] = []
        self.is_running = False

        # Crash recovery coordination
        self.worker_health_monitor_task: Optional[asyncio.Task] = None
        self.crash_recovery_enabled = True
        self.health_check_interval = 60  # seconds

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

        # Start worker health monitoring for crash recovery
        if self.crash_recovery_enabled:
            self.worker_health_monitor_task = asyncio.create_task(self._monitor_worker_health())
            self.tasks.append(self.worker_health_monitor_task)

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

    async def _monitor_worker_health(self):
        """Monitor worker health for crash recovery coordination"""
        while self.is_running:
            try:
                await self._check_worker_health_and_recover()
                await asyncio.sleep(self.health_check_interval)
            except Exception as e:
                logger.error(f"Error in worker health monitor: {e}")
                await asyncio.sleep(10)

    async def _check_worker_health_and_recover(self):
        """Check all workers' health and recover jobs from crashed workers"""
        logger.debug("Checking worker health for crash recovery")

        try:
            # Get all jobs that are marked as running
            jobs = await self.queue.list_jobs()
            running_jobs = [job for job in jobs if job.status == JobStatus.RUNNING]

            if not running_jobs:
                return  # No running jobs to check

            # Collect all active workers' heartbeats
            active_workers = {}
            for worker in self.workers:
                if worker.is_running:
                    # Share heartbeat data between workers for crash detection
                    for wid, heartbeat_data in worker.worker_registry.items():
                        active_workers[wid] = heartbeat_data

            # Check each running job for crashed worker
            recovered_count = 0
            for job in running_jobs:
                worker_id = job.metadata.get("assigned_worker")
                if not worker_id:
                    continue

                # Check if worker is healthy
                if worker_id not in active_workers:
                    # Worker not found in registry - assume crashed
                    logger.warning(f"Job {job.id} assigned to unknown worker {worker_id}, recovering")
                    await self._recover_job_from_crashed_worker(job)
                    recovered_count += 1
                else:
                    # Check heartbeat age
                    worker_data = active_workers[worker_id]
                    last_heartbeat = datetime.fromisoformat(worker_data["timestamp"])
                    time_since_heartbeat = datetime.now() - last_heartbeat

                    max_age = timedelta(seconds=self.workers[0].heartbeat_interval * 2)
                    if time_since_heartbeat > max_age:
                        logger.warning(f"Job {job.id} assigned to stale worker {worker_id}, recovering")
                        await self._recover_job_from_crashed_worker(job)
                        recovered_count += 1

            if recovered_count > 0:
                logger.info(f"Worker pool recovered {recovered_count} jobs from crashed/stale workers")

        except Exception as e:
            logger.error(f"Error in worker health check: {e}")

    async def _recover_job_from_crashed_worker(self, job: Job):
        """Recover a job from a crashed worker"""
        try:
            logger.info(f"Recovering job {job.id} from crashed worker")

            # Reset job status to queued for reassignment
            job.update_status(JobStatus.QUEUED)
            await self.queue.update_job_status(job.id, JobStatus.QUEUED)

            # Clear worker assignment
            job.metadata.pop("assigned_worker", None)
            job.metadata.pop("assigned_at", None)

            # Add recovery metadata
            job.metadata["recovered_at"] = datetime.now().isoformat()
            job.metadata["recovery_reason"] = "worker_crash"

            logger.info(f"Job {job.id} successfully recovered and queued for reassignment")

        except Exception as e:
            logger.error(f"Failed to recover job {job.id}: {e}")

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
