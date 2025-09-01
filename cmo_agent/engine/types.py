from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class JobSpec:
    goal: str
    budget_usd: float = 10.0
    autopilot_level: int = 2
    target_leads: Optional[int] = None
    target_emails: Optional[int] = None
    created_by: str = "cli"
    constraints: Dict[str, Any] = field(default_factory=dict)
    dry_run: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "metadata": {
                "created_by": self.created_by,
                "autopilot_level": self.autopilot_level,
                "budget_per_day": self.budget_usd,
                "target_leads": self.target_leads,
                "target_emails": self.target_emails,
                "constraints": self.constraints,
                "dry_run": self.dry_run,
            },
        }


@dataclass
class RunSummary:
    ok: bool = True
    stats: Dict[str, Any] = field(default_factory=dict)
    errors: list = field(default_factory=list)

"""
Shared types for unified CLI/Web execution
Single source of truth for job specifications and results
"""
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List
from datetime import datetime
from enum import Enum


class JobStatus(Enum):
    """Job execution status"""
    PENDING = "pending"
    QUEUED = "queued" 
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


@dataclass
class JobSpec:
    """Complete job specification - single source of truth"""
    goal: str
    constraints: Dict[str, Any] = field(default_factory=dict)
    budget_usd: float = 10.0
    autopilot_level: int = 0  # 0-3 autonomy level
    dry_run: bool = False
    config_path: Optional[str] = None
    seed_repos: Optional[List[str]] = None
    target_leads: Optional[int] = None
    target_emails: Optional[int] = None
    
    # Execution preferences
    max_repos: int = 200
    max_api_calls: int = 1000
    timeout_minutes: int = 30
    
    # Metadata
    created_by: str = "user"
    priority: int = 0
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for API/storage"""
        return {
            "goal": self.goal,
            "constraints": self.constraints,
            "budget_usd": self.budget_usd,
            "autopilot_level": self.autopilot_level,
            "dry_run": self.dry_run,
            "config_path": self.config_path,
            "seed_repos": self.seed_repos,
            "target_leads": self.target_leads,
            "target_emails": self.target_emails,
            "max_repos": self.max_repos,
            "max_api_calls": self.max_api_calls,
            "timeout_minutes": self.timeout_minutes,
            "created_by": self.created_by,
            "priority": self.priority,
            "tags": self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobSpec':
        """Create from dict"""
        return cls(
            goal=data["goal"],
            constraints=data.get("constraints", {}),
            budget_usd=data.get("budget_usd", 10.0),
            autopilot_level=data.get("autopilot_level", 0),
            dry_run=data.get("dry_run", False),
            config_path=data.get("config_path"),
            seed_repos=data.get("seed_repos"),
            target_leads=data.get("target_leads"),
            target_emails=data.get("target_emails"),
            max_repos=data.get("max_repos", 200),
            max_api_calls=data.get("max_api_calls", 1000),
            timeout_minutes=data.get("timeout_minutes", 30),
            created_by=data.get("created_by", "user"),
            priority=data.get("priority", 0),
            tags=data.get("tags", [])
        )


@dataclass 
class RunSummary:
    """Standardized job execution summary"""
    ok: bool
    job_id: str
    duration_seconds: float
    
    # Core metrics
    stats: Dict[str, Any] = field(default_factory=dict)  # steps, api_calls, leads, emails_prepared, etc.
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    # Results
    repos_found: int = 0
    candidates_found: int = 0
    leads_with_emails: int = 0
    emails_prepared: int = 0
    
    # Artifacts
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    
    # Raw state for advanced use cases
    final_state: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for API responses"""
        return {
            "ok": self.ok,
            "job_id": self.job_id,
            "duration_seconds": self.duration_seconds,
            "stats": self.stats,
            "warnings": self.warnings,
            "errors": self.errors,
            "repos_found": self.repos_found,
            "candidates_found": self.candidates_found,
            "leads_with_emails": self.leads_with_emails,
            "emails_prepared": self.emails_prepared,
            "artifacts": self.artifacts,
            "final_state": self.final_state
        }


@dataclass
class JobEvent:
    """Unified event schema for both CLI and Web SSE"""
    type: str  # "job.queued" | "job.started" | "tool.started" | "tool.completed" | "progress" | "job.completed" | "error"
    ts: float  # Unix timestamp
    data: Dict[str, Any]
    job_id: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for SSE/JSON"""
        return {
            "type": self.type,
            "ts": self.ts,
            "data": self.data,
            "job_id": self.job_id
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'JobEvent':
        """Create from dict"""
        return cls(
            type=data["type"],
            ts=data["ts"], 
            data=data["data"],
            job_id=data["job_id"]
        )
    
    # Factory methods for common events
    @classmethod
    def job_started(cls, job_id: str, goal: str) -> 'JobEvent':
        return cls("job.started", time.time(), {"goal": goal}, job_id)
    
    @classmethod
    def tool_started(cls, job_id: str, tool_name: str) -> 'JobEvent':
        return cls("tool.started", time.time(), {"tool_name": tool_name}, job_id)
    
    @classmethod
    def progress(cls, job_id: str, stage: str, current_item: str = "", progress_pct: float = 0) -> 'JobEvent':
        return cls("progress", time.time(), {
            "stage": stage,
            "current_item": current_item,
            "progress_pct": progress_pct
        }, job_id)
    
    @classmethod
    def job_completed(cls, job_id: str, summary: RunSummary) -> 'JobEvent':
        return cls("job.completed", time.time(), summary.to_dict(), job_id)


# Import time at module level
import time
