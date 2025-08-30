"""
RunState - Typed state management for CMO Agent
"""
from typing import TypedDict, List, Dict, Optional, Any
from datetime import datetime


class RunState(TypedDict, total=False):
    """Typed state for CMO Agent LangGraph workflow"""

    # Job metadata
    job_id: str
    goal: str
    created_at: str
    created_by: str

    # ICP (Ideal Customer Profile) criteria
    icp: Dict[str, Any]  # keywords, languages, stars, activity window

    # Discovery phase
    repos: List[Dict[str, Any]]  # GitHub repositories found
    candidates: List[Dict[str, Any]]  # {login, from_repo, signal}

    # Enrichment phase
    leads: List[Dict[str, Any]]  # enriched + scored prospects

    # Personalization phase
    to_send: List[Dict[str, Any]]  # {email, subject, body, meta}

    # Execution reports
    reports: Dict[str, Any]  # instantly/attio/linear/export reports

    # Error handling
    errors: List[Dict[str, Any]]  # {stage, payload, error, timestamp}

    # Monitoring & metrics
    counters: Dict[str, int]  # {steps, api_calls, tokens}
    checkpoints: List[str]  # artifact ids / CSV paths

    # Configuration
    config: Dict[str, Any]  # caps, pacing, retries

    # Control flow
    ended: bool
    current_stage: str
    history: List[Dict[str, Any]]  # conversation history


class JobMetadata:
    """Job metadata and configuration"""

    def __init__(self, goal: str, created_by: str = "user"):
        self.job_id = f"cmo-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.goal = goal
        self.created_at = datetime.now().isoformat()
        self.created_by = created_by

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "goal": self.goal,
            "created_at": self.created_at,
            "created_by": self.created_by,
        }


# Default configuration values
DEFAULT_CONFIG = {
    "max_steps": 40,
    "max_repos": 600,
    "max_people": 3000,
    "per_inbox_daily": 50,
    "activity_days": 90,
    "stars_range": "100..2000",
    "languages": ["python"],
    "include_topics": ["ci", "testing", "pytest", "devtools", "llm"],
    "rate_limits": {
        "github_per_hour": 5000,
        "instantly_per_inbox_daily": 50,
        "attio_per_minute": 60,
        "linear_per_minute": 30,
    },
    "timeouts": {
        "github_api": 15,
        "instantly_api": 30,
        "attio_api": 20,
        "linear_api": 20,
    },
    "retries": {
        "max_attempts": 3,
        "backoff_multiplier": 2.0,
        "jitter": True,
    },
}
