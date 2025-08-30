#!/usr/bin/env python3
"""
CMO Agent Execution Engine - Run jobs with async workers
"""
import asyncio
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path
parent_dir = str(Path(__file__).parent.parent)
sys.path.insert(0, parent_dir)

from core.job import JobManager, JobStatus, ProgressInfo
from core.queue import InMemoryJobQueue, JobController
from core.persistent_queue import PersistentJobQueue
from core.worker import WorkerPool
from core.monitoring import record_job_submitted, MetricsLogger, get_global_collector
try:
    from agents.cmo_agent import CMOAgent
except ImportError:
    from ..agents.cmo_agent import CMOAgent
from core.state import DEFAULT_CONFIG

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('./logs/execution_engine.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)


class ExecutionEngine:
    """Main execution engine for CMO Agent jobs"""

    def __init__(self, num_workers: int = 3):
        self.num_workers = num_workers

        # Initialize components
        self.job_manager = JobManager()
        self.queue = PersistentJobQueue()
        self.controller = JobController(self.queue)
        self.worker_pool: Optional[WorkerPool] = None
        self.agent: Optional[CMOAgent] = None
        self.metrics_logger: Optional[MetricsLogger] = None

        # State
        self.is_running = False
        self._shutdown_event = asyncio.Event()

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        self._shutdown_event.set()

    async def initialize(self, config_path: Optional[str] = None):
        """Initialize the execution engine"""
        try:
            # Load configuration
            config = DEFAULT_CONFIG.copy()
            if config_path and Path(config_path).exists():
                import yaml
                with open(config_path, 'r') as f:
                    file_config = yaml.safe_load(f)
                    config.update(file_config)

            # Initialize CMO Agent
            self.agent = CMOAgent(config)
            logger.info("CMO Agent initialized")

            # Initialize worker pool
            self.worker_pool = WorkerPool(
                num_workers=self.num_workers,
                queue=self.queue,
                agent=self.agent
            )
            logger.info(f"Worker pool initialized with {self.num_workers} workers")

            return True

        except Exception as e:
            logger.error(f"Failed to initialize execution engine: {e}")
            return False

    async def start(self):
        """Start the execution engine"""
        if not self.agent:
            raise RuntimeError("Engine not initialized. Call initialize() first.")

        self.is_running = True
        logger.info("Starting CMO Agent Execution Engine...")

        try:
                    # Start worker pool
        await self.worker_pool.start(self.agent)

        # Start metrics logger
        self.metrics_logger = MetricsLogger(get_global_collector(), log_interval=60)
        asyncio.create_task(self.metrics_logger.start_logging())

        # Start job processing loop
        await self._run_main_loop()

        except Exception as e:
            logger.error(f"Execution engine error: {e}")
        finally:
            # Cleanup
            if self.worker_pool:
                await self.worker_pool.stop()
            if self.metrics_logger:
                self.metrics_logger.stop_logging()
            self.is_running = False
            logger.info("Execution engine stopped")

    async def _run_main_loop(self):
        """Main processing loop"""
        logger.info("Execution engine running. Press Ctrl+C to stop.")

        while self.is_running and not self._shutdown_event.is_set():
            try:
                # Process any pending operations
                await self._process_pending_operations()

                # Small delay to prevent busy waiting
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(5)

    async def _process_pending_operations(self):
        """Process any pending operations"""
        # This could include:
        # - Checking for stuck jobs
        # - Updating job statuses
        # - Processing completed jobs
        # - Logging statistics

        # For now, just log stats periodically
        stats = await self.queue.get_queue_stats()
        if stats["total_jobs"] > 0:
            logger.info(f"Queue stats: {stats}")

    async def submit_job(self, goal: str, created_by: str = "user", priority: int = 0) -> str:
        """Submit a new job for execution"""
        try:
            # Create job
            job = self.job_manager.create_job(goal, created_by)

            # Record job submission
            record_job_submitted()

            # Add progress callback
            async def progress_callback(progress_info):
                job.update_progress(**progress_info)

            # Set progress callback on agent (if supported)
            if hasattr(self.agent, 'set_progress_callback'):
                self.agent.set_progress_callback(progress_callback)

            # Enqueue job
            job_id = await self.queue.enqueue_job(job, priority)

            logger.info(f"Job submitted: {job_id} - {goal[:50]}...")
            return job_id

        except Exception as e:
            logger.error(f"Failed to submit job: {e}")
            raise

    async def get_job_status(self, job_id: str) -> Optional[dict]:
        """Get job status and progress"""
        # Get job from queue (which is the source of truth after enqueuing)
        jobs = await self.queue.list_jobs()
        job = next((j for j in jobs if j.id == job_id), None)
        if not job:
            return None

        progress = await self.queue.get_job_progress(job_id)

        return {
            "job_id": job.id,
            "status": job.status.value,
            "goal": job.goal,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "progress": progress.to_dict() if progress else None,
            "artifacts": job.artifacts,
        }

    async def list_jobs(self, status_filter: Optional[JobStatus] = None) -> list:
        """List jobs with optional status filter"""
        # Get jobs from queue (source of truth after enqueuing)
        jobs = await self.queue.list_jobs(status_filter)
        result = []
        for job in jobs:
            status = await self.get_job_status(job.id)
            if status:
                result.append(status)
        return result

    async def pause_job(self, job_id: str) -> bool:
        """Pause a running job"""
        return await self.controller.pause_job(job_id)

    async def resume_job(self, job_id: str) -> bool:
        """Resume a paused job"""
        return await self.controller.resume_job(job_id)

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job"""
        return await self.controller.cancel_job(job_id)

    async def get_stats_async(self) -> dict:
        """Get execution engine statistics (async version)"""
        worker_stats = self.worker_pool.get_stats() if self.worker_pool else {}

        # Get queue stats for job counts (queue is source of truth)
        queue_stats = await self.queue.get_queue_stats() if self.queue else {}

        return {
            "engine_status": "running" if self.is_running else "stopped",
            "workers": worker_stats,
            "jobs": {
                "total": queue_stats.get("total_jobs", 0),
                "by_status": queue_stats.get("jobs_by_status", {}),
            },
            "queue": queue_stats,
        }

    def get_stats(self) -> dict:
        """Get execution engine statistics"""
        # This method is synchronous, so we need to handle the async call differently
        # For now, return basic stats without queue details
        worker_stats = self.worker_pool.get_stats() if self.worker_pool else {}

        return {
            "engine_status": "running" if self.is_running else "stopped",
            "workers": worker_stats,
            "jobs": {
                "total": 0,  # Will be updated when queue stats are available
                "by_status": {},
            },
            "queue": {},
        }


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="CMO Agent Execution Engine")
    parser.add_argument(
        "--config",
        "-c",
        help="Path to configuration file"
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=3,
        help="Number of worker processes (default: 3)"
    )
    parser.add_argument(
        "--job",
        "-j",
        help="Submit a job and exit (don't start engine)"
    )
    parser.add_argument(
        "--status",
        "-s",
        help="Get job status and exit"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all jobs and exit"
    )
    parser.add_argument(
        "--start-workers",
        action="store_true",
        help="Start worker pool to process jobs (use with --job to submit and process)"
    )
    parser.add_argument(
        "--workers-only",
        action="store_true",
        help="Start only the worker pool (no job submission)"
    )

    args = parser.parse_args()

    # Create execution engine
    engine = ExecutionEngine(num_workers=args.workers)

    # Initialize
    if not await engine.initialize(args.config):
        print("❌ Failed to initialize execution engine")
        return 1

    # Handle one-off commands
    if args.job and not args.start_workers:
        job_id = await engine.submit_job(args.job)
        print(f"✅ Job submitted: {job_id}")
        print("💡 Job queued for processing. Use --start-workers to process it now.")
        return 0

    if args.status:
        status = await engine.get_job_status(args.status)
        if status:
            print(f"📋 Job Status: {status['status']}")
            print(f"🎯 Goal: {status['goal']}")
            if status['progress']:
                progress = status['progress']
                print(f"📊 Stage: {progress['stage']}")
                print(f"🔢 Step: {progress['step']}")
                print(f"📈 Metrics: {progress['metrics']}")
        else:
            print(f"❌ Job not found: {args.status}")
        return 0

    if args.list:
        jobs = await engine.list_jobs()
        if jobs:
            print(f"📋 Jobs ({len(jobs)} total):")
            for job in jobs:
                print(f"  {job['job_id'][:8]} - {job['status']} - {job['goal'][:40]}...")
        else:
            print("📋 No jobs found")
        return 0

    # Submit job and start workers if requested
    if args.job and args.start_workers:
        job_id = await engine.submit_job(args.job)
        print(f"✅ Job submitted: {job_id}")
        print("🚀 Starting worker pool to process job...")

        # Start the engine with workers
        try:
            await engine.start()
        except KeyboardInterrupt:
            print("\n🛑 Shutdown requested by user")
        except Exception as e:
            print(f"\n💥 Engine crashed: {e}")
            return 1

        print("\n👋 Execution engine shutdown complete")
        return 0

    # Start workers only (if requested)
    if args.workers_only:
        try:
            await engine.start()
        except KeyboardInterrupt:
            print("\n🛑 Shutdown requested by user")
        except Exception as e:
            print(f"\n💥 Engine crashed: {e}")
            return 1

        print("\n👋 Worker pool shutdown complete")
        return 0

    # Start the engine (if no one-off commands)
    try:
        await engine.start()
    except KeyboardInterrupt:
        print("\n🛑 Shutdown requested by user")
    except Exception as e:
        print(f"\n💥 Engine crashed: {e}")
        return 1

    print("\n👋 Execution engine shutdown complete")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
