"""
Monitoring and metrics system for CMO Agent
"""
import time
import psutil
import asyncio
import logging
import json
from typing import Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, field

from .job import JobStatus


@dataclass
class MetricsSnapshot:
    """Enhanced snapshot of system metrics at a point in time"""
    timestamp: datetime = field(default_factory=datetime.now)

    # Job lifecycle metrics
    jobs_submitted: int = 0
    jobs_completed: int = 0
    jobs_failed: int = 0
    jobs_paused: int = 0
    jobs_cancelled: int = 0
    jobs_running: int = 0
    jobs_queued: int = 0
    jobs_recovered: int = 0  # From crash recovery

    # Performance metrics
    throughput_jobs_per_hour: float = 0.0
    avg_job_duration_seconds: float = 0.0
    median_job_duration_seconds: float = 0.0
    p95_job_duration_seconds: float = 0.0
    worker_utilization_percent: float = 0.0

    # Queue metrics
    queue_depth: int = 0
    avg_queue_wait_time_seconds: float = 0.0
    queue_processing_rate: float = 0.0  # jobs/second

    # API metrics
    api_calls_total: int = 0
    api_calls_successful: int = 0
    api_call_success_rate: float = 0.0
    api_calls_by_endpoint: Dict[str, int] = field(default_factory=dict)
    api_rate_limits_hit: int = 0

    # Resource metrics
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used_mb: float = 0.0
    disk_usage_percent: float = 0.0
    network_bytes_sent: int = 0
    network_bytes_recv: int = 0

    # Worker metrics
    workers_active: int = 0
    workers_total: int = 0
    worker_crash_count: int = 0
    avg_jobs_per_worker: float = 0.0

    # Error metrics
    error_rate_percent: float = 0.0
    errors_by_component: Dict[str, int] = field(default_factory=dict)
    errors_by_type: Dict[str, int] = field(default_factory=dict)
    critical_errors: int = 0

    # Checkpoint metrics
    checkpoints_created: int = 0
    checkpoints_restored: int = 0
    checkpoint_failures: int = 0

    # Business metrics
    leads_processed_total: int = 0
    leads_enriched_total: int = 0
    repos_discovered_total: int = 0
    emails_sent_total: int = 0

    # Alert conditions
    alerts_active: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/serialization"""
        data = {
            "timestamp": self.timestamp.isoformat(),
            "jobs": {
                "submitted": self.jobs_submitted,
                "completed": self.jobs_completed,
                "failed": self.jobs_failed,
                "paused": self.jobs_paused,
                "cancelled": self.jobs_cancelled,
                "running": self.jobs_running,
                "queued": self.jobs_queued,
                "recovered": self.jobs_recovered,
                "throughput_per_hour": self.throughput_jobs_per_hour,
                "avg_duration_seconds": self.avg_job_duration_seconds,
                "median_duration_seconds": self.median_job_duration_seconds,
                "p95_duration_seconds": self.p95_job_duration_seconds,
            },
            "performance": {
                "worker_utilization_percent": self.worker_utilization_percent,
                "queue_depth": self.queue_depth,
                "avg_queue_wait_seconds": self.avg_queue_wait_time_seconds,
                "queue_processing_rate": self.queue_processing_rate,
            },
            "api": {
                "calls_total": self.api_calls_total,
                "calls_successful": self.api_calls_successful,
                "success_rate_percent": self.api_call_success_rate,
                "calls_by_endpoint": self.api_calls_by_endpoint,
                "rate_limits_hit": self.api_rate_limits_hit,
            },
            "resources": {
                "cpu_percent": self.cpu_percent,
                "memory_percent": self.memory_percent,
                "memory_used_mb": self.memory_used_mb,
                "disk_usage_percent": self.disk_usage_percent,
                "network_bytes_sent": self.network_bytes_sent,
                "network_bytes_recv": self.network_bytes_recv,
            },
            "workers": {
                "active": self.workers_active,
                "total": self.workers_total,
                "crash_count": self.worker_crash_count,
                "avg_jobs_per_worker": self.avg_jobs_per_worker,
            },
            "errors": {
                "rate_percent": self.error_rate_percent,
                "by_component": self.errors_by_component,
                "by_type": self.errors_by_type,
                "critical_errors": self.critical_errors,
            },
            "checkpoints": {
                "created": self.checkpoints_created,
                "restored": self.checkpoints_restored,
                "failures": self.checkpoint_failures,
            },
            "business": {
                "leads_processed": self.leads_processed_total,
                "leads_enriched": self.leads_enriched_total,
                "repos_discovered": self.repos_discovered_total,
                "emails_sent": self.emails_sent_total,
            },
            "alerts": {
                "active": self.alerts_active,
            },
        }
        return data


class MetricsCollector:
    """Enhanced metrics collector with alerting and structured logging"""

    def __init__(self):
        self.snapshots: List[MetricsSnapshot] = []
        self.start_time = time.time()
        self.correlation_id = None

        # Job lifecycle tracking
        self.jobs_submitted = 0
        self.jobs_completed = 0
        self.jobs_failed = 0
        self.jobs_paused = 0
        self.jobs_cancelled = 0
        self.jobs_recovered = 0
        self.job_durations: List[float] = []
        self.current_jobs_running = 0
        self.current_queue_depth = 0

        # API tracking
        self.api_calls_total = 0
        self.api_calls_successful = 0
        self.api_calls_by_endpoint: Dict[str, int] = {}
        self.api_rate_limits_hit = 0

        # Worker tracking
        self.workers_active = 0
        self.workers_total = 0
        self.worker_crash_count = 0

        # Error tracking
        self.errors_total = 0
        self.errors_by_component: Dict[str, int] = {}
        self.errors_by_type: Dict[str, int] = {}
        self.critical_errors = 0

        # Checkpoint tracking
        self.checkpoints_created = 0
        self.checkpoints_restored = 0
        self.checkpoint_failures = 0

        # Business metrics
        self.leads_processed_total = 0
        self.leads_enriched_total = 0
        self.repos_discovered_total = 0
        self.emails_sent_total = 0

        # Alert system
        self.alerts_active: List[str] = []
        self.alert_thresholds = {
            "error_rate_threshold": 0.1,  # 10% error rate
            "queue_depth_threshold": 100,
            "memory_usage_threshold": 0.9,  # 90% memory usage
            "worker_crash_threshold": 3,  # Max crashes per hour
        }

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
        self.record_error(component, "job_failure")

    def record_job_paused(self):
        """Record a job pause"""
        self.jobs_paused += 1

    def record_job_cancelled(self):
        """Record a job cancellation"""
        self.jobs_cancelled += 1

    def record_job_recovered(self):
        """Record a job recovery from crash"""
        self.jobs_recovered += 1

    def record_api_call(self, successful: bool = True, endpoint: str = None):
        """Record an API call"""
        self.api_calls_total += 1
        if successful:
            self.api_calls_successful += 1
        if endpoint:
            self.api_calls_by_endpoint[endpoint] = self.api_calls_by_endpoint.get(endpoint, 0) + 1

    def record_api_rate_limit_hit(self):
        """Record an API rate limit hit"""
        self.api_rate_limits_hit += 1

    def record_worker_crash(self):
        """Record a worker crash"""
        self.worker_crash_count += 1

    def record_checkpoint_created(self):
        """Record a checkpoint creation"""
        self.checkpoints_created += 1

    def record_checkpoint_restored(self):
        """Record a checkpoint restoration"""
        self.checkpoints_restored += 1

    def record_checkpoint_failure(self):
        """Record a checkpoint failure"""
        self.checkpoint_failures += 1

    def record_business_metrics(self, leads_processed: int = 0, leads_enriched: int = 0,
                               repos_discovered: int = 0, emails_sent: int = 0):
        """Record business metrics"""
        self.leads_processed_total += leads_processed
        self.leads_enriched_total += leads_enriched
        self.repos_discovered_total += repos_discovered
        self.emails_sent_total += emails_sent

    def record_error(self, component: str, error_type: str = "unknown", is_critical: bool = False):
        """Record an error by component and type"""
        self.errors_total += 1
        self.errors_by_component[component] = self.errors_by_component.get(component, 0) + 1
        self.errors_by_type[error_type] = self.errors_by_type.get(error_type, 0) + 1
        if is_critical:
            self.critical_errors += 1

    def update_current_state(self, jobs_running: int, queue_depth: int):
        """Update current state metrics"""
        self.current_jobs_running = jobs_running
        self.current_queue_depth = queue_depth

    def collect_snapshot(self) -> MetricsSnapshot:
        """Collect an enhanced metrics snapshot with alerting"""
        snapshot = MetricsSnapshot()

        # Job lifecycle metrics
        snapshot.jobs_submitted = self.jobs_submitted
        snapshot.jobs_completed = self.jobs_completed
        snapshot.jobs_failed = self.jobs_failed
        snapshot.jobs_paused = self.jobs_paused
        snapshot.jobs_cancelled = self.jobs_cancelled
        snapshot.jobs_running = self.current_jobs_running
        snapshot.jobs_queued = self.current_queue_depth
        snapshot.jobs_recovered = self.jobs_recovered

        # Performance metrics
        elapsed_hours = (time.time() - self.start_time) / 3600
        if elapsed_hours > 0:
            snapshot.throughput_jobs_per_hour = self.jobs_completed / elapsed_hours

        if self.job_durations:
            sorted_durations = sorted(self.job_durations)
            snapshot.avg_job_duration_seconds = sum(self.job_durations) / len(self.job_durations)
            snapshot.median_job_duration_seconds = sorted_durations[len(sorted_durations) // 2]
            p95_index = int(len(sorted_durations) * 0.95)
            snapshot.p95_job_duration_seconds = sorted_durations[min(p95_index, len(sorted_durations) - 1)]

        # Queue metrics
        snapshot.queue_depth = self.current_queue_depth
        # Calculate processing rate (simplified)
        if elapsed_hours > 0:
            snapshot.queue_processing_rate = self.jobs_completed / (elapsed_hours * 3600)

        # API metrics
        snapshot.api_calls_total = self.api_calls_total
        snapshot.api_calls_successful = self.api_calls_successful
        snapshot.api_calls_by_endpoint = self.api_calls_by_endpoint.copy()
        snapshot.api_rate_limits_hit = self.api_rate_limits_hit
        if self.api_calls_total > 0:
            snapshot.api_call_success_rate = (self.api_calls_successful / self.api_calls_total) * 100

        # Resource metrics
        snapshot.cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        snapshot.memory_percent = memory.percent
        snapshot.memory_used_mb = memory.used / (1024 * 1024)
        snapshot.disk_usage_percent = psutil.disk_usage('/').percent

        # Network stats (if available)
        try:
            net = psutil.net_io_counters()
            snapshot.network_bytes_sent = net.bytes_sent
            snapshot.network_bytes_recv = net.bytes_recv
        except Exception:
            pass

        # Worker metrics
        snapshot.workers_active = self.workers_active
        snapshot.workers_total = self.workers_total
        snapshot.worker_crash_count = self.worker_crash_count
        if self.workers_active > 0:
            snapshot.avg_jobs_per_worker = (self.jobs_completed + self.jobs_failed) / self.workers_active

        # Error metrics
        total_operations = self.jobs_submitted + self.api_calls_total
        if total_operations > 0:
            snapshot.error_rate_percent = (self.errors_total / total_operations) * 100

        snapshot.errors_by_component = self.errors_by_component.copy()
        snapshot.errors_by_type = self.errors_by_type.copy()
        snapshot.critical_errors = self.critical_errors

        # Checkpoint metrics
        snapshot.checkpoints_created = self.checkpoints_created
        snapshot.checkpoints_restored = self.checkpoints_restored
        snapshot.checkpoint_failures = self.checkpoint_failures

        # Business metrics
        snapshot.leads_processed_total = self.leads_processed_total
        snapshot.leads_enriched_total = self.leads_enriched_total
        snapshot.repos_discovered_total = self.repos_discovered_total
        snapshot.emails_sent_total = self.emails_sent_total

        # Generate alerts
        snapshot.alerts_active = self._check_alerts(snapshot)

        # Store snapshot
        self.snapshots.append(snapshot)

        return snapshot

    def _check_alerts(self, snapshot: MetricsSnapshot) -> List[str]:
        """Check for alert conditions and return active alerts"""
        alerts = []

        # Error rate alert
        if snapshot.error_rate_percent > (self.alert_thresholds["error_rate_threshold"] * 100):
            alerts.append(f"High error rate: {snapshot.error_rate_percent:.1f}%")

        # Queue depth alert
        if snapshot.queue_depth > self.alert_thresholds["queue_depth_threshold"]:
            alerts.append(f"High queue depth: {snapshot.queue_depth}")

        # Memory usage alert
        if snapshot.memory_percent > (self.alert_thresholds["memory_usage_threshold"] * 100):
            alerts.append(f"High memory usage: {snapshot.memory_percent:.1f}%")

        # Worker crash alert
        if snapshot.worker_crash_count > self.alert_thresholds["worker_crash_threshold"]:
            alerts.append(f"High worker crash rate: {snapshot.worker_crash_count}")

        # API success rate alert
        if snapshot.api_call_success_rate < 95.0 and snapshot.api_calls_total > 10:
            alerts.append(f"Low API success rate: {snapshot.api_call_success_rate:.1f}%")

        return alerts


class StructuredLogger:
    """Enhanced structured logging with correlation IDs"""

    def __init__(self, collector: MetricsCollector = None):
        self.collector = collector or get_global_collector()
        import logging
        self.logger = logging.getLogger(__name__)

    def log_job_event(self, event: str, job_id: str, **kwargs):
        """Log a job-related event with structured data"""
        correlation_id = kwargs.pop('correlation_id', job_id)
        log_data = {
            "event": event,
            "job_id": job_id,
            "correlation_id": correlation_id,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.logger.info(f"Job {event}: {job_id}", extra={"structured": log_data})

    def log_error(self, error: Exception, component: str, **kwargs):
        """Log an error with structured data"""
        correlation_id = kwargs.pop('correlation_id', None)
        log_data = {
            "event": "error",
            "component": component,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "correlation_id": correlation_id,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.logger.error(f"Error in {component}: {error}", extra={"structured": log_data})

    def log_performance_metric(self, metric: str, value: float, **kwargs):
        """Log a performance metric"""
        correlation_id = kwargs.pop('correlation_id', None)
        log_data = {
            "event": "performance_metric",
            "metric": metric,
            "value": value,
            "correlation_id": correlation_id,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.logger.info(f"Performance: {metric} = {value}", extra={"structured": log_data})

    def log_business_event(self, event: str, **kwargs):
        """Log a business-related event"""
        correlation_id = kwargs.pop('correlation_id', None)
        log_data = {
            "event": event,
            "correlation_id": correlation_id,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        self.logger.info(f"Business event: {event}", extra={"structured": log_data})


class MetricsLogger:
    """Enhanced metrics logger with structured output"""

    def __init__(self, collector: MetricsCollector, log_interval: int = 60):
        self.collector = collector
        self.log_interval = log_interval
        self.is_running = False
        self.structured_logger = StructuredLogger(collector)

    async def start_logging(self):
        """Start periodic metrics logging with structured output"""
        self.is_running = True

        while self.is_running:
            try:
                snapshot = self.collector.collect_snapshot()
                metrics_dict = snapshot.to_dict()

                # Log structured metrics snapshot
                self.structured_logger.logger.info(
                    "Metrics snapshot collected",
                    extra={"metrics": metrics_dict}
                )

                # Log any active alerts
                if snapshot.alerts_active:
                    for alert in snapshot.alerts_active:
                        self.structured_logger.logger.warning(
                            f"Alert triggered: {alert}",
                            extra={"alert": alert, "metrics": metrics_dict}
                        )

                await asyncio.sleep(self.log_interval)

            except Exception as e:
                self.structured_logger.logger.error(f"Metrics logging error: {e}")
                await asyncio.sleep(self.log_interval)

    def stop_logging(self):
        """Stop metrics logging"""
        self.is_running = False


# Global instances
_global_collector = MetricsCollector()
_global_logger = StructuredLogger(_global_collector)

def get_global_collector() -> MetricsCollector:
    """Get the global metrics collector"""
    return _global_collector

def get_global_logger() -> StructuredLogger:
    """Get the global structured logger"""
    return _global_logger

# Job lifecycle recording functions
def record_job_submitted():
    """Record a job submission"""
    _global_collector.record_job_submitted()

def record_job_completed(duration_seconds: float):
    """Record a job completion"""
    _global_collector.record_job_completed(duration_seconds)

def record_job_failed(component: str = "unknown"):
    """Record a job failure"""
    _global_collector.record_job_failed(component)

def record_job_paused():
    """Record a job pause"""
    _global_collector.record_job_paused()

def record_job_cancelled():
    """Record a job cancellation"""
    _global_collector.record_job_cancelled()

def record_job_recovered():
    """Record a job recovery from crash"""
    _global_collector.record_job_recovered()

# API tracking functions
def record_api_call(successful: bool = True, endpoint: str = None):
    """Record an API call"""
    _global_collector.record_api_call(successful, endpoint)

def record_api_rate_limit_hit():
    """Record an API rate limit hit"""
    _global_collector.record_api_rate_limit_hit()

# Worker and system functions
def record_worker_crash():
    """Record a worker crash"""
    _global_collector.record_worker_crash()

def record_checkpoint_created():
    """Record a checkpoint creation"""
    _global_collector.record_checkpoint_created()

def record_checkpoint_restored():
    """Record a checkpoint restoration"""
    _global_collector.record_checkpoint_restored()

def record_checkpoint_failure():
    """Record a checkpoint failure"""
    _global_collector.record_checkpoint_failure()

# Business metrics functions
def record_business_metrics(leads_processed: int = 0, leads_enriched: int = 0,
                           repos_discovered: int = 0, emails_sent: int = 0):
    """Record business metrics"""
    _global_collector.record_business_metrics(leads_processed, leads_enriched,
                                            repos_discovered, emails_sent)

# Error recording functions
def record_error(component: str, error_type: str = "unknown", is_critical: bool = False):
    """Record an error by component and type"""
    _global_collector.record_error(component, error_type, is_critical)

# Structured logging functions
def log_job_event(event: str, job_id: str, **kwargs):
    """Log a job-related event with structured data"""
    _global_logger.log_job_event(event, job_id, **kwargs)

def log_error(error: Exception, component: str, **kwargs):
    """Log an error with structured data"""
    _global_logger.log_error(error, component, **kwargs)

def log_performance_metric(metric: str, value: float, **kwargs):
    """Log a performance metric"""
    _global_logger.log_performance_metric(metric, value, **kwargs)

def log_business_event(event: str, **kwargs):
    """Log a business-related event"""
    _global_logger.log_business_event(event, **kwargs)


# ---------- JSON Formatter for file logging ----------
class JsonExtraFormatter(logging.Formatter):
    """JSON formatter that includes structured extras such as 'structured', 'metrics', and 'alert'.
    
    Produces JSON Lines suitable for ingestion.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        base: Dict[str, Any] = {
            "ts": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        
        # Include common extras when present
        if hasattr(record, "structured") and isinstance(record.structured, dict):
            base.update(record.structured)
        if hasattr(record, "metrics") and isinstance(record.metrics, dict):
            base["metrics"] = record.metrics
        if hasattr(record, "alert") and record.alert:
            base["alert"] = record.alert
            
        # Attach exception info if present
        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)
            
        return json.dumps(base, ensure_ascii=False)
