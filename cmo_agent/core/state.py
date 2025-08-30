"""
RunState - Typed state management for CMO Agent
"""
from typing import TypedDict, List, Dict, Optional, Any
from datetime import datetime
from pathlib import Path
import json
import hashlib
import time


STATE_VERSION = 1


class ErrorEntry(TypedDict, total=False):
    stage: str
    tool: Optional[str]
    payload: Dict[str, Any]
    error: str
    timestamp: str
    retry_count: Optional[int]
    category: Optional[str]  # retryable | rate_limit | permanent


class CheckpointMeta(TypedDict, total=False):
    id: str
    created_at: str
    stage: Optional[str]
    type: str  # periodic | error | final | manual
    reason: Optional[str]
    path: str


class RunState(TypedDict, total=False):
    """Typed state for CMO Agent LangGraph workflow"""

    # Job metadata
    job_id: str
    goal: str
    created_at: str
    created_by: str

    # Versioning
    state_version: int

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
    errors: List[ErrorEntry]  # structured errors

    # Monitoring & metrics
    counters: Dict[str, int]  # {steps, api_calls, tokens}
    checkpoints: List[str]  # artifact ids / CSV paths
    checkpoints_meta: List[CheckpointMeta]

    # Configuration
    config: Dict[str, Any]  # caps, pacing, retries

    # Control flow
    ended: bool
    current_stage: str
    history: List[Dict[str, Any]]  # conversation history

    # Idempotency & privacy
    idempotency_keys: Dict[str, str]
    privacy: Dict[str, Any]


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
        "max_backoff_seconds": 300,  # 5 minutes max
        "rate_limit_retry_after": 60,  # Wait 60s after rate limit
    },
    "error_handling": {
        "retryable_errors": [
            "ConnectionError",
            "TimeoutError",
            "httpx.ConnectTimeout",
            "httpx.ReadTimeout",
            "httpx.PoolTimeout",
            "aiohttp.ClientConnectorError",
        ],
        "rate_limit_errors": [
            "RateLimitError",
            "TooManyRequests",
            "GitHubRateLimitError",
            "CircuitBreakerOpenError",
        ],
        "permanent_errors": [
            "AuthenticationError",
            "AuthorizationError",
            "NotFoundError",
            "ValidationError",
        ],
        "circuit_breaker": {
            "failure_threshold": 5,
            "recovery_timeout": 300,  # 5 minutes
            "expected_exception": Exception,
        },
    },
    "directories": {
        "exports": "./exports",
        "checkpoints": "./checkpoints",
        "logs": "./logs",
        "artifacts": "./artifacts",
    },
}


def migrate_run_state(state: Dict[str, Any]) -> RunState:
    """Migrate an incoming state dict to the current schema with sane defaults.

    This function is idempotent and can be safely called at load boundaries.
    """
    # Base copy
    migrated: RunState = {**state}  # type: ignore

    # Versioning
    if "state_version" not in migrated:
        migrated["state_version"] = STATE_VERSION

    # Collections & structures
    migrated.setdefault("repos", [])
    migrated.setdefault("candidates", [])
    migrated.setdefault("leads", [])
    migrated.setdefault("to_send", [])
    migrated.setdefault("reports", {})
    migrated.setdefault("errors", [])
    migrated.setdefault("counters", {})
    migrated.setdefault("checkpoints", [])
    migrated.setdefault("checkpoints_meta", [])
    migrated.setdefault("config", DEFAULT_CONFIG)
    migrated.setdefault("ended", False)
    migrated.setdefault("current_stage", "initialization")
    migrated.setdefault("history", [])
    migrated.setdefault("idempotency_keys", {})
    migrated.setdefault("privacy", {"redact_pii": True, "pii_fields": ["email", "phone"]})

    # Ensure error entries are shaped
    normalized_errors: List[ErrorEntry] = []
    for err in migrated.get("errors", []):
        if isinstance(err, dict):
            normalized_errors.append(ErrorEntry(
                stage=err.get("stage", migrated.get("current_stage", "unknown")),
                tool=err.get("tool"),
                payload=err.get("payload", {}),
                error=str(err.get("error", "")),
                timestamp=err.get("timestamp", datetime.now().isoformat()),
                retry_count=err.get("retry_count"),
                category=err.get("category"),
            ))
        else:
            normalized_errors.append(ErrorEntry(
                stage=migrated.get("current_stage", "unknown"),
                payload={},
                error=str(err),
                timestamp=datetime.now().isoformat(),
            ))
    migrated["errors"] = normalized_errors

    return migrated


def _get_checkpoint_dir(state: RunState, checkpoint_dir: Optional[str] = None) -> Path:
    if checkpoint_dir:
        return Path(checkpoint_dir)
    config_dirs = (state.get("config") or {}).get("directories", {})  # type: ignore
    return Path(config_dirs.get("checkpoints", DEFAULT_CONFIG["directories"]["checkpoints"]))


def save_checkpoint(job_id: str, state: RunState, *, checkpoint_dir: Optional[str] = None, type: str = "periodic", reason: str = "") -> str:
    """Persist a JSON checkpoint and update state metadata.

    Returns the file path written.
    """
    directory = _get_checkpoint_dir(state, checkpoint_dir)
    directory.mkdir(parents=True, exist_ok=True)

    checkpoint_id = f"{job_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{type}"
    file_path = directory / f"{checkpoint_id}.json"

    # Always migrate before writing so schema is stable
    state_to_write = migrate_run_state(state)

    with open(file_path, "w") as f:
        json.dump(state_to_write, f, indent=2, default=str)

    # Update lists (immutably expected by callers; we still return path)
    state.setdefault("checkpoints", [])
    state["checkpoints"].append(str(file_path))  # type: ignore

    state.setdefault("checkpoints_meta", [])
    state["checkpoints_meta"].append(CheckpointMeta(  # type: ignore
        id=checkpoint_id,
        created_at=datetime.now().isoformat(),
        stage=state.get("current_stage"),
        type=type,
        reason=reason,
        path=str(file_path),
    ))

    return str(file_path)


def load_latest_checkpoint(job_id: str, *, checkpoint_dir: Optional[str] = None) -> Optional[RunState]:
    """Load the latest checkpoint for a job, if one exists.

    Prefers `checkpoints_meta` ordering; falls back to scanning the directory.
    """
    base_dir = Path(checkpoint_dir) if checkpoint_dir else Path(DEFAULT_CONFIG["directories"]["checkpoints"]) 

    if not base_dir.exists():
        return None

    # Find all files for this job
    candidates = sorted(base_dir.glob(f"{job_id}-*.json"), reverse=True)
    for fp in candidates:
        try:
            with open(fp, "r") as f:
                loaded = json.load(f)
            return migrate_run_state(loaded)
        except Exception:
            continue
    return None


def make_idempotency_key(job_id: str, stage: str, target_identifier: str, payload: Dict[str, Any]) -> str:
    """Create a stable idempotency fingerprint.

    hash(job_id, stage, target_identifier, payload_hash)
    """
    payload_str = json.dumps(payload or {}, separators=(",", ":"), sort_keys=True)
    payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    material = "|".join([job_id, stage, target_identifier, payload_hash])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class RetryConfig:
    """Configuration for retry behavior"""

    def __init__(self, config: Dict[str, Any]):
        retry_config = config.get("retries", {})
        self.max_attempts = retry_config.get("max_attempts", 3)
        self.backoff_multiplier = retry_config.get("backoff_multiplier", 2.0)
        self.jitter = retry_config.get("jitter", True)
        self.max_backoff_seconds = retry_config.get("max_backoff_seconds", 300)
        self.rate_limit_retry_after = retry_config.get("rate_limit_retry_after", 60)

    def get_backoff_delay(self, attempt: int) -> float:
        """Calculate backoff delay for given attempt number"""
        delay = self.backoff_multiplier ** attempt

        # Apply jitter if enabled
        if self.jitter:
            import random
            delay *= (0.5 + random.random() * 0.5)  # 0.5 to 1.0 multiplier

        # Cap at maximum backoff
        return min(delay, self.max_backoff_seconds)


class ErrorHandler:
    """Advanced error handling with retry logic and circuit breaker"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.error_handling_config = config.get("error_handling", {})
        self.retry_config = RetryConfig(config)

        # Circuit breaker state
        self.circuit_breaker_config = self.error_handling_config.get("circuit_breaker", {})
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "closed"  # closed, open, half_open

        # API-specific error handler
        self.api_error_handler = APIErrorHandler(config)

    def is_retryable_error(self, error: Exception) -> bool:
        """Check if an error is retryable"""
        error_type = type(error).__name__
        retryable_errors = self.error_handling_config.get("retryable_errors", [])
        return error_type in retryable_errors or any(
            issubclass(type(error), globals().get(err_type, type(None)))
            for err_type in retryable_errors
        )

    def is_rate_limit_error(self, error: Exception) -> bool:
        """Check if error is due to rate limiting"""
        error_type = type(error).__name__
        rate_limit_errors = self.error_handling_config.get("rate_limit_errors", [])
        return error_type in rate_limit_errors

    def is_permanent_error(self, error: Exception) -> bool:
        """Check if error is permanent and shouldn't be retried"""
        error_type = type(error).__name__
        permanent_errors = self.error_handling_config.get("permanent_errors", [])
        return error_type in permanent_errors

    async def execute_with_retry(self, func, *args, **kwargs):
        """Execute a function with retry logic"""
        last_error = None

        for attempt in range(self.retry_config.max_attempts):
            try:
                # Check circuit breaker
                if not self.can_execute():
                    raise CircuitBreakerOpenError("Circuit breaker is open")

                result = await func(*args, **kwargs)
                self.on_success()
                return result

            except Exception as e:
                last_error = e
                self.on_failure(e)

                # Don't retry permanent errors
                if self.is_permanent_error(e):
                    break

                # Calculate retry delay
                if self.is_rate_limit_error(e):
                    delay = self.retry_config.rate_limit_retry_after
                elif self.is_retryable_error(e):
                    delay = self.retry_config.get_backoff_delay(attempt)
                else:
                    break  # Don't retry unknown errors

                if attempt < self.retry_config.max_attempts - 1:
                    import asyncio
                    await asyncio.sleep(delay)

        # All retries exhausted
        raise last_error

    def can_execute(self) -> bool:
        """Check if circuit breaker allows execution"""
        if self.state == "closed":
            return True
        elif self.state == "open":
            # Check if recovery timeout has passed
            import time
            recovery_timeout = self.circuit_breaker_config.get("recovery_timeout", 300)
            if time.time() - self.last_failure_time > recovery_timeout:
                self.state = "half_open"
                return True
            return False
        elif self.state == "half_open":
            return True
        return False

    def on_success(self):
        """Handle successful execution"""
        if self.state == "half_open":
            self.state = "closed"
            self.failure_count = 0

    def on_failure(self, error: Exception):
        """Handle failed execution"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        failure_threshold = self.circuit_breaker_config.get("failure_threshold", 5)
        if self.failure_count >= failure_threshold:
            self.state = "open"


class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open"""
    pass


class RateLimitDetector:
    """Detect and handle rate limiting from various APIs"""

    @staticmethod
    def is_rate_limited(response_or_error) -> tuple[bool, float]:
        """Check if a response indicates rate limiting and return retry-after time"""
        retry_after = 60.0  # Default retry after

        # Handle HTTP responses
        if hasattr(response_or_error, 'status_code'):
            if response_or_error.status_code == 429:
                # Check for Retry-After header
                retry_after_header = response_or_error.headers.get('Retry-After')
                if retry_after_header:
                    try:
                        retry_after = float(retry_after_header)
                    except ValueError:
                        pass
                return True, retry_after

        # Handle GitHub API rate limit
        if hasattr(response_or_error, 'headers'):
            rate_limit_remaining = response_or_error.headers.get('X-RateLimit-Remaining')
            rate_limit_reset = response_or_error.headers.get('X-RateLimit-Reset')

            if rate_limit_remaining and rate_limit_remaining == '0' and rate_limit_reset:
                try:
                    import time
                    reset_time = int(rate_limit_reset)
                    retry_after = max(0, reset_time - time.time())
                    return True, retry_after
                except (ValueError, TypeError):
                    pass

        # Handle common rate limit error messages
        error_str = str(response_or_error).lower()
        rate_limit_indicators = [
            'rate limit exceeded',
            'too many requests',
            'api rate limit',
            'request rate exceeded',
            'rate_limit',
            '429',
        ]

        for indicator in rate_limit_indicators:
            if indicator in error_str:
                return True, retry_after

        return False, 0.0


class GitHubRateLimitError(Exception):
    """Exception for GitHub API rate limiting"""
    def __init__(self, message: str, retry_after: float = 60.0):
        super().__init__(message)
        self.retry_after = retry_after


class APIErrorHandler:
    """Specialized error handler for API interactions"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.rate_limits = config.get("rate_limits", {})

    async def handle_api_error(self, error: Exception, api_name: str, context: Dict[str, Any] = None):
        """Handle API-specific errors with appropriate retry logic"""
        context = context or {}

        # Check for rate limiting
        is_rate_limited, retry_after = RateLimitDetector.is_rate_limited(error)

        if is_rate_limited:
            # Create appropriate rate limit error
            if api_name.lower() == 'github':
                raise GitHubRateLimitError(f"GitHub API rate limit exceeded", retry_after)
            else:
                raise Exception(f"{api_name} API rate limit exceeded, retry after {retry_after}s")

        # Handle authentication errors
        if self._is_auth_error(error):
            raise Exception(f"{api_name} authentication failed: {error}")

        # Handle network errors
        if self._is_network_error(error):
            raise error  # Let retry logic handle this

        # Handle other API errors
        raise Exception(f"{api_name} API error: {error}")

    def _is_auth_error(self, error: Exception) -> bool:
        """Check if error is authentication-related"""
        error_str = str(error).lower()
        auth_indicators = [
            'unauthorized',
            'forbidden',
            'authentication',
            'invalid token',
            'bad credentials',
            '401',
            '403',
        ]
        return any(indicator in error_str for indicator in auth_indicators)

    def _is_network_error(self, error: Exception) -> bool:
        """Check if error is network-related"""
        error_type = type(error).__name__
        network_errors = [
            'ConnectionError',
            'TimeoutError',
            'ConnectTimeout',
            'ReadTimeout',
            'PoolTimeout',
            'ClientConnectorError',
        ]
        return error_type in network_errors
