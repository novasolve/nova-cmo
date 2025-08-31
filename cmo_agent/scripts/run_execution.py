#!/usr/bin/env python3
"""
CMO Agent Execution Engine - Run jobs with async workers
"""
import asyncio
import logging
import signal
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any

# Add parent directory to path
parent_dir = str(Path(__file__).parent.parent)
sys.path.insert(0, parent_dir)
# Also add project root to path to support absolute imports when invoked from subdir
project_root = str(Path(__file__).resolve().parents[2])
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.job import JobManager, JobStatus, ProgressInfo
from core.queue import InMemoryJobQueue, JobController
from core.persistent_queue import PersistentJobQueue
from core.worker import WorkerPool
from core.monitoring import record_job_submitted, MetricsLogger, get_global_collector
try:
    # Prefer absolute package import to ensure relative imports inside module resolve
    from cmo_agent.agents.cmo_agent import CMOAgent
except Exception:
    try:
        from agents.cmo_agent import CMOAgent
    except Exception:
        # Avoid relative import beyond top-level package - use absolute import instead
        import sys
        from pathlib import Path
        project_root = str(Path(__file__).resolve().parents[2])
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
        from cmo_agent.agents.cmo_agent import CMOAgent
from core.state import DEFAULT_CONFIG
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# Setup logging (configurable)
from core.monitoring import JsonExtraFormatter, configure_metrics_from_config
from core.state import DEFAULT_CONFIG as _DEF

def _setup_logging_from_config(cfg: dict):
    log_cfg = cfg.get("logging", {}) if isinstance(cfg.get("logging"), dict) else {}
    log_level = getattr(logging, str(log_cfg.get("level", "INFO")).upper(), logging.INFO)
    logs_dir = Path(cfg.get("directories", _DEF.get("directories", {})).get("logs", "./logs"))
    logs_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(log_level)

    # Clear existing handlers to avoid duplicates in repeated CLI invocations
    for h in root.handlers[:]:
        root.removeHandler(h)

    # Console handler (human-readable)
    ch = logging.StreamHandler()
    ch.setLevel(log_level)
    ch.setFormatter(logging.Formatter(log_cfg.get("console_format", "%(asctime)s %(levelname)-4s %(message)s")))
    root.addHandler(ch)

    # File handler (JSON lines with extras)
    if log_cfg.get("json_file", True):
        fh_path = logs_dir / log_cfg.get("execution_log_file", "execution_engine.jsonl")
        fh = logging.FileHandler(str(fh_path), encoding="utf-8")
        fh.setLevel(log_level)
        fh.setFormatter(JsonExtraFormatter())
        root.addHandler(fh)

_setup_logging_from_config(DEFAULT_CONFIG)
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

            # Overlay environment variables (take precedence over file)
            env_mapping = {
                'GITHUB_TOKEN': 'GITHUB_TOKEN',
                'INSTANTLY_API_KEY': 'INSTANTLY_API_KEY',
                'ATTIO_API_KEY': 'ATTIO_API_KEY',
                'ATTIO_WORKSPACE_ID': 'ATTIO_WORKSPACE_ID',
                'LINEAR_API_KEY': 'LINEAR_API_KEY',
                'OPENAI_API_KEY': 'OPENAI_API_KEY',
                # Optional extras referenced in README
                'STATE_DB_URL': 'STATE_DB_URL',
                'BLOB_DIR': 'BLOB_DIR',
                'LANGFUSE_SERVER_URL': 'LANGFUSE_SERVER_URL',
                'LANGFUSE_PUBLIC_KEY': 'LANGFUSE_PUBLIC_KEY',
                'LANGFUSE_SECRET_KEY': 'LANGFUSE_SECRET_KEY',
            }
            for config_key, env_var in env_mapping.items():
                env_val = os.getenv(env_var)
                if env_val:
                    config[config_key] = env_val

            # Ensure directories exist (logs, checkpoints, artifacts, exports)
            from core.state import DEFAULT_CONFIG as _DEF
            dirs = config.get("directories", _DEF.get("directories", {}))
            for key in ["logs", "checkpoints", "artifacts", "exports"]:
                try:
                    path = Path(dirs.get(key, _DEF["directories"].get(key, f"./{key}")))
                    path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    logger.warning(f"Failed to ensure directory for {key}: {e}")

            # Reconfigure logging with loaded config
            _setup_logging_from_config(config)
            # Apply monitoring thresholds
            configure_metrics_from_config(config)

            # Initialize queue with configured storage dir if provided
            try:
                q_cfg = config.get("queue", {})
                storage_dir = q_cfg.get("storage_dir", "./data/jobs")
                self.queue = PersistentJobQueue(storage_dir=storage_dir)
            except Exception as e:
                logger.warning(f"Falling back to default PersistentJobQueue: {e}")

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

            # Start artifact cleanup task if enabled
            try:
                from core.artifacts import get_artifact_manager
                self._artifact_manager = get_artifact_manager(config)
                artifacts_cfg = config.get("artifacts", {})
                if artifacts_cfg.get("auto_cleanup", True):
                    await self._artifact_manager.start_cleanup_task()
                    logger.info("Artifact cleanup task started")
            except Exception as e:
                logger.warning(f"Artifact cleanup task not started: {e}")

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

            # Start metrics logger based on config
            monitoring_cfg = getattr(self.agent, "config", {}).get("monitoring", {})
            if monitoring_cfg.get("enabled", True):
                interval = int(monitoring_cfg.get("metrics_interval", 60))
                self.metrics_logger = MetricsLogger(get_global_collector(), log_interval=interval)
                # Optional Prometheus exporter
                if monitoring_cfg.get("enable_prometheus", False):
                    port = int(monitoring_cfg.get("prometheus_port", 8000))
                    try:
                        self.metrics_logger.enable_prometheus(port)
                    except Exception as e:
                        logger.warning(f"Prometheus exporter not enabled: {e}")
                asyncio.create_task(self.metrics_logger.start_logging())
                logger.info(f"Metrics logger started (interval={interval}s)")

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
            # Stop artifact cleanup task
            try:
                if hasattr(self, "_artifact_manager") and self._artifact_manager:
                    await self._artifact_manager.stop_cleanup_task()
            except Exception:
                pass
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

    async def submit_job(self, goal: str, created_by: str = "user", priority: int = 0, metadata: Dict[str, Any] = None, config_path: str = None) -> str:
        """Submit a new job for execution"""
        try:
            # Create job with metadata
            logger.info(f"Creating job with metadata: {metadata}")
            job = self.job_manager.create_job(goal, created_by, metadata=metadata, config_path=config_path)
            logger.info(f"Created job {job.id} with metadata: {job.metadata}")

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
            "metadata": job.metadata,
        }

    async def list_jobs(self, status_filter: Optional[JobStatus] = None) -> list:
        """List jobs with optional status filter"""
        # Get jobs from queue (source of truth after enqueuing)
        jobs = await self.queue.list_jobs(status_filter)
        result = []
        for job in jobs:
            progress = await self.queue.get_job_progress(job.id)
            job_data = {
                "job_id": job.id,
                "status": job.status.value,
                "goal": job.goal,
                "created_at": job.created_at.isoformat(),
                "updated_at": job.updated_at.isoformat(),
                "progress": progress.to_dict() if progress else None,
                "artifacts": job.artifacts,
                "metadata": job.metadata,
            }
            result.append(job_data)
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
