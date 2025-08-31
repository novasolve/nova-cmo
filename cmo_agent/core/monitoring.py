"""
Monitoring and metrics system for CMO Agent
"""
import time
import psutil
import asyncio
from typing import Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, field

from .job import JobStatus


@dataclass
class MetricsSnapshot:
    """Snapshot of system metrics at a point in time"""
    timestamp: datetime = field(default_factory=datetime.now)

    # Job metrics
    jobs_submitted: int = 0
    jobs_completed: int = 0
    jobs_failed: int = 0
    jobs_running: int = 0
    jobs_queued: int = 0

    # Performance metrics
    throughput_jobs_per_hour: float = 0.0
    avg_job_duration_seconds: float = 0.0
    worker_utilization_percent: float = 0.0

    # Queue metrics
    queue_depth: int = 0
    avg_queue_wait_time_seconds: float = 0.0

    # API metrics
    api_calls_total: int = 0
    api_calls_successful: int = 0
    api_call_success_rate: float = 0.0

    # Resource metrics
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_usage_percent: float = 0.0

    # Error metrics
    error_rate_percent: float = 0.0
    errors_by_component: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/serialization"""
        data = {
            "timestamp": self.timestamp.isoformat(),
            "jobs": {
                "submitted": self.jobs_submitted,
                "completed": self.jobs_completed,
                "failed": self.jobs_failed,
                "running": self.jobs_running,
                "queued": self.jobs_queued,
                "throughput_per_hour": self.throughput_jobs_per_hour,
                "avg_duration_seconds": self.avg_job_duration_seconds,
            },
            "performance": {
                "worker_utilization_percent": self.worker_utilization_percent,
                "queue_depth": self.queue_depth,
                "avg_queue_wait_seconds": self.avg_queue_wait_time_seconds,
            },
            "api": {
                "calls_total": self.api_calls_total,
                "calls_successful": self.api_calls_successful,
                "success_rate_percent": self.api_call_success_rate,
            },
            "resources": {
                "cpu_percent": self.cpu_percent,
                "memory_percent": self.memory_percent,
                "disk_usage_percent": self.disk_usage_percent,
            },
            "errors": {
                "rate_percent": self.error_rate_percent,
                "by_component": self.errors_by_component,
            },
        }
        return data


class MetricsCollector:
    """Collects and aggregates metrics"""

    def __init__(self):
        self.snapshots: List[MetricsSnapshot] = []
        self.start_time = time.time()

        # Job tracking
        self.jobs_submitted = 0
        self.jobs_completed = 0
        self.jobs_failed = 0
        self.job_durations: List[float] = []
        self.current_jobs_running = 0
        self.current_queue_depth = 0

        # API tracking
        self.api_calls_total = 0
        self.api_calls_successful = 0

        # Error tracking
        self.errors_total = 0
        self.errors_by_component: Dict[str, int] = {}

    def record_job_submitted(self):
        """Record a job submission"""
        self.jobs_submitted += 1

    def record_job_completed(self, duration_seconds: float):
        """Record a job completion"""
        self.jobs_completed += 1
        self.job_durations.append(duration_seconds)

    def record_job_failed(self, component: str = "unknown"):
        """Record a job failure"""
        self.jobs_failed += 1
        self.record_error(component)

    def record_api_call(self, successful: bool = True):
        """Record an API call"""
        self.api_calls_total += 1
        if successful:
            self.api_calls_successful += 1

    def record_error(self, component: str):
        """Record an error by component"""
        self.errors_total += 1
        self.errors_by_component[component] = self.errors_by_component.get(component, 0) + 1

    def update_current_state(self, jobs_running: int, queue_depth: int):
        """Update current state metrics"""
        self.current_jobs_running = jobs_running
        self.current_queue_depth = queue_depth

    def collect_snapshot(self) -> MetricsSnapshot:
        """Collect a metrics snapshot"""
        snapshot = MetricsSnapshot()

        # Job metrics
        snapshot.jobs_submitted = self.jobs_submitted
        snapshot.jobs_completed = self.jobs_completed
        snapshot.jobs_failed = self.jobs_failed
        snapshot.jobs_running = self.current_jobs_running
        snapshot.jobs_queued = self.current_queue_depth

        # Performance metrics
        elapsed_hours = (time.time() - self.start_time) / 3600
        if elapsed_hours > 0:
            snapshot.throughput_jobs_per_hour = self.jobs_completed / elapsed_hours

        if self.job_durations:
            snapshot.avg_job_duration_seconds = sum(self.job_durations) / len(self.job_durations)

        # Queue metrics
        snapshot.queue_depth = self.current_queue_depth

        # API metrics
        snapshot.api_calls_total = self.api_calls_total
        snapshot.api_calls_successful = self.api_calls_successful
        if self.api_calls_total > 0:
            snapshot.api_call_success_rate = (self.api_calls_successful / self.api_calls_total) * 100

        # Resource metrics
        snapshot.cpu_percent = psutil.cpu_percent(interval=1)
        snapshot.memory_percent = psutil.virtual_memory().percent
        snapshot.disk_usage_percent = psutil.disk_usage('/').percent

        # Error metrics
        total_operations = self.jobs_submitted + self.api_calls_total
        if total_operations > 0:
            snapshot.error_rate_percent = (self.errors_total / total_operations) * 100

        snapshot.errors_by_component = self.errors_by_component.copy()

        # Store snapshot
        self.snapshots.append(snapshot)

        return snapshot


class MetricsLogger:
    """Logs metrics in structured format"""

    def __init__(self, collector: MetricsCollector, log_interval: int = 60):
        self.collector = collector
        self.log_interval = log_interval
        self.is_running = False

    async def start_logging(self):
        """Start periodic metrics logging"""
        self.is_running = True
        import logging
        logger = logging.getLogger(__name__)

        while self.is_running:
            try:
                snapshot = self.collector.collect_snapshot()
                metrics_dict = snapshot.to_dict()

                # Log structured metrics
                logger.info("Metrics snapshot", extra={"metrics": metrics_dict})

                await asyncio.sleep(self.log_interval)

            except Exception as e:
                logger.error(f"Metrics logging error: {e}")
                await asyncio.sleep(self.log_interval)

    def stop_logging(self):
        """Stop metrics logging"""
        self.is_running = False


# Global metrics collector
_global_collector = MetricsCollector()

def get_global_collector() -> MetricsCollector:
    """Get the global metrics collector"""
    return _global_collector

def record_job_submitted():
    """Record a job submission"""
    _global_collector.record_job_submitted()

def record_job_completed(duration_seconds: float):
    """Record a job completion"""
    _global_collector.record_job_completed(duration_seconds)

def record_job_failed(component: str = "unknown"):
    """Record a job failure"""
    _global_collector.record_job_failed(component)

def record_api_call(successful: bool = True):
    """Record an API call"""
    _global_collector.record_api_call(successful)

def record_error(component: str):
    """Record an error by component"""
    _global_collector.record_error(component)
