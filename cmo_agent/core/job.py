"""
Job management system for CMO Agent
"""
import uuid
from enum import Enum
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from .state import RunState, JobMetadata


class JobStatus(Enum):
    """Job status enumeration"""
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProgressInfo:
    """Progress information for job execution"""
    job_id: str
    stage: str = ""
    step: int = 0
    total_steps: Optional[int] = None
    current_item: str = ""
    items_processed: int = 0
    items_total: Optional[int] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    estimated_completion: Optional[datetime] = None
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "job_id": self.job_id,
            "stage": self.stage,
            "step": self.step,
            "total_steps": self.total_steps,
            "current_item": self.current_item,
            "items_processed": self.items_processed,
            "items_total": self.items_total,
            "metrics": self.metrics,
            "artifacts": self.artifacts,
            "errors": self.errors,
            "estimated_completion": self.estimated_completion.isoformat() if self.estimated_completion else None,
            "last_updated": self.last_updated.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProgressInfo':
        """Create from dictionary"""
        if data.get("estimated_completion"):
            data["estimated_completion"] = datetime.fromisoformat(data["estimated_completion"])
        data["last_updated"] = datetime.fromisoformat(data["last_updated"])
        return cls(**data)


@dataclass
class Job:
    """Job representation"""
    id: str
    goal: str
    status: JobStatus
    config: Dict[str, Any]
    metadata: Dict[str, Any]
    run_state: Optional[RunState] = None
    artifacts: List[str] = field(default_factory=list)
    progress: ProgressInfo = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Initialize progress info if not provided"""
        if self.progress is None:
            self.progress = ProgressInfo(job_id=self.id)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "id": self.id,
            "goal": self.goal,
            "status": self.status.value,
            "config": self.config,
            "metadata": self.metadata,
            "run_state": self.run_state,
            "artifacts": self.artifacts,
            "progress": self.progress.to_dict() if self.progress else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Job':
        """Create from dictionary"""
        data["status"] = JobStatus(data["status"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if data.get("progress"):
            data["progress"] = ProgressInfo.from_dict(data["progress"])
        if data.get("run_state") and isinstance(data["run_state"], dict):
            # Convert run_state dict to RunState if needed
            data["run_state"] = RunState(**data["run_state"])
        return cls(**data)

    @classmethod
    def create(cls, goal: str, created_by: str = "user", config: Dict[str, Any] = None, metadata: Dict[str, Any] = None) -> 'Job':
        """Create a new job"""
        job_id = f"cmo-{uuid.uuid4().hex[:8]}"
        base_metadata = {
            "created_by": created_by,
            "priority": "normal",
            "tags": [],
        }
        # Merge provided metadata with base metadata
        if metadata:
            base_metadata.update(metadata)
        config = config or {}

        return cls(
            id=job_id,
            goal=goal,
            status=JobStatus.QUEUED,
            config=config,
            metadata=base_metadata,
            progress=ProgressInfo(job_id=job_id, stage="created"),
        )

    def update_status(self, status: JobStatus):
        """Update job status and timestamp"""
        self.status = status
        self.updated_at = datetime.now()

    def add_artifact(self, artifact_path: str):
        """Add an artifact to the job"""
        if artifact_path not in self.artifacts:
            self.artifacts.append(artifact_path)
        self.updated_at = datetime.now()

    def update_progress(self, **kwargs):
        """Update progress information"""
        for key, value in kwargs.items():
            if hasattr(self.progress, key):
                setattr(self.progress, key, value)
        self.progress.last_updated = datetime.now()
        self.updated_at = datetime.now()

    def mark_completed(self, final_state: RunState = None):
        """Mark job as completed"""
        self.status = JobStatus.COMPLETED
        if final_state:
            self.run_state = final_state
        self.updated_at = datetime.now()

    def mark_failed(self, error: str = None):
        """Mark job as failed"""
        self.status = JobStatus.FAILED
        if error and self.progress:
            self.progress.errors.append(error)
        self.updated_at = datetime.now()

    def pause(self):
        """Pause the job"""
        if self.status == JobStatus.RUNNING:
            self.status = JobStatus.PAUSED
            self.updated_at = datetime.now()

    def resume(self):
        """Resume the job"""
        if self.status == JobStatus.PAUSED:
            self.status = JobStatus.RUNNING
            self.updated_at = datetime.now()

    def cancel(self):
        """Cancel the job"""
        if self.status in [JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.PAUSED]:
            self.status = JobStatus.CANCELLED
            self.updated_at = datetime.now()

    @property
    def duration(self) -> Optional[timedelta]:
        """Get job duration if completed"""
        if self.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            return self.updated_at - self.created_at
        return None

    @property
    def is_active(self) -> bool:
        """Check if job is currently active"""
        return self.status in [JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.PAUSED]

    @property
    def is_finished(self) -> bool:
        """Check if job is finished"""
        return self.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]


class JobManager:
    """Job management interface"""

    def __init__(self):
        self.jobs: Dict[str, Job] = {}
        self._listeners: List[callable] = []

    def create_job(self, goal: str, created_by: str = "user", config: Dict[str, Any] = None, metadata: Dict[str, Any] = None, config_path: str = None) -> Job:
        """Create a new job"""
        # If config_path is provided, load config from file
        if config_path and not config:
            try:
                import yaml
                from pathlib import Path
                config_file = Path(config_path)
                if config_file.exists():
                    with open(config_file, 'r') as f:
                        config = yaml.safe_load(f)
            except Exception as e:
                # Log warning but continue with default config
                import logging
                logging.getLogger(__name__).warning(f"Failed to load config from {config_path}: {e}")
        
        job = Job.create(goal, created_by, config=config, metadata=metadata)
        self.jobs[job.id] = job
        self._notify_listeners("job_created", job)
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID"""
        return self.jobs.get(job_id)

    def list_jobs(self, status_filter: Optional[JobStatus] = None) -> List[Job]:
        """List all jobs, optionally filtered by status"""
        jobs = list(self.jobs.values())
        if status_filter:
            jobs = [job for job in jobs if job.status == status_filter]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    def update_job_status(self, job_id: str, status: JobStatus):
        """Update job status"""
        job = self.jobs.get(job_id)
        if job:
            old_status = job.status
            job.update_status(status)
            self._notify_listeners("job_status_updated", job, old_status)

    def add_job_listener(self, listener: callable):
        """Add a job event listener"""
        self._listeners.append(listener)

    def remove_job_listener(self, listener: callable):
        """Remove a job event listener"""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify_listeners(self, event: str, job: Job, *args):
        """Notify all listeners of job events"""
        for listener in self._listeners:
            try:
                listener(event, job, *args)
            except Exception as e:
                print(f"Error in job listener: {e}")  # Use logging in production
