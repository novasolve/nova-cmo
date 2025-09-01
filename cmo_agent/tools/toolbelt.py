"""
Toolbelt: centralized tool execution with idempotency, retries, timeouts,
privacy redaction, and structured metrics/logging.
"""
import asyncio
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

try:
    # Prefer package-relative imports
    from .base import BaseTool, ToolResult
except Exception:
    # Fallback minimal stubs (for isolated runs)
    class ToolResult:
        def __init__(self, success: bool, data: Any = None, error: str = None, metadata: Dict = None):
            self.success = success
            self.data = data or {}
            self.error = error
            self.metadata = metadata or {}
            self.timestamp = datetime.now().isoformat()

        def to_dict(self) -> Dict[str, Any]:
            return {
                "success": self.success,
                "data": self.data,
                "error": self.error,
                "metadata": self.metadata,
                "timestamp": self.timestamp,
            }

    class BaseTool:  # type: ignore
        async def execute(self, **kwargs) -> ToolResult:
            return ToolResult(True, data={})

try:
    # Monitoring hooks (optional)
    from ..core.monitoring import (
        log_job_event,
        log_error,
        log_business_event,
        record_error,
    )
except Exception:
    # No-op fallbacks
    def log_job_event(event: str, job_id: str, **kwargs):
        pass

    def log_error(error: Exception, component: str, **kwargs):
        pass

    def log_business_event(event: str, **kwargs):
        pass

    def record_error(component: str, error_type: str = "unknown", is_critical: bool = False):
        pass

try:
    # Error handling with circuit breaker and retries (optional)
    from ..core.state import ErrorHandler
except Exception:
    class ErrorHandler:
        def __init__(self, config: Dict[str, Any] = None):
            self.config = config or {}

        async def execute_with_retry(self, coro_factory, *args, **kwargs):
            max_attempts = self.config.get("retries", {}).get("max_attempts", 3)
            delay_seconds = 1.0
            attempt = 0
            while True:
                try:
                    return await coro_factory()
                except Exception as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        raise
                    await asyncio.sleep(delay_seconds)
                    delay_seconds *= 2


def _stable_hash(data: Any) -> str:
    try:
        payload = json.dumps(data, sort_keys=True, default=str)
    except Exception:
        payload = str(data)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _redact(obj: Any, pii_fields: Optional[list]) -> Any:
    if not pii_fields:
        return obj

    if isinstance(obj, dict):
        return {k: ("<redacted>" if k in pii_fields else _redact(v, pii_fields)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(v, pii_fields) for v in obj]
    return obj


class _IdempotencyCache:
    def __init__(self, ttl_seconds: int = 3600):
        self.ttl = timedelta(seconds=ttl_seconds)
        self._store: Dict[str, Dict[str, Any]] = {}

    def get(self, key: str) -> Optional[ToolResult]:
        entry = self._store.get(key)
        if not entry:
            return None
        if datetime.now() - entry["ts"] > self.ttl:
            # Expired
            self._store.pop(key, None)
            return None
        return entry["result"]

    def set(self, key: str, result: ToolResult):
        self._store[key] = {"ts": datetime.now(), "result": result}


class Toolbelt:
    """Central orchestrator for tool execution with robust behaviors."""

    def __init__(self, tools: Dict[str, BaseTool], config: Dict[str, Any] = None):
        self.tools = tools or {}
        self.config = config or {}
        self.error_handler = ErrorHandler(self.config)
        ttl = self.config.get("tools", {}).get("idempotency_ttl_seconds", 3600)
        self.idempotency_cache = _IdempotencyCache(ttl_seconds=ttl)

    def register_tool(self, name: str, tool: BaseTool):
        self.tools[name] = tool

    def compute_idempotency_key(self, tool_name: str, args: Dict[str, Any]) -> str:
        base = {"tool": tool_name, "args": args}
        return _stable_hash(base)

    async def execute(
        self,
        tool_name: str,
        *,
        job_id: Optional[str] = None,
        args: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        redact_pii: bool = True,
    ) -> ToolResult:
        args = args or {}
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' is not registered")

        # Compute idempotency key
        idem_key = idempotency_key or self.compute_idempotency_key(tool_name, args)
        cached = self.idempotency_cache.get(idem_key)
        if cached:
            log_job_event("tool_cache_hit", job_id or "unknown", tool=tool_name, idempotency_key=idem_key)
            return cached

        # Privacy redaction for logging only
        pii_fields = []
        if redact_pii:
            pii_fields = self.config.get("privacy", {}).get("pii_fields", ["email", "phone"])
            safe_args = _redact(args, pii_fields)
        else:
            safe_args = args

        log_job_event("tool_started", job_id or "unknown", tool=tool_name, args=safe_args)

        tool = self.tools[tool_name]

        async def _run_tool():
            # Prefer the tool's internal retry + rate limiter to ensure spacing on each attempt
            max_attempts = (
                self.config.get("retries", {}).get("max_attempts", 3)
                if isinstance(self.config.get("retries"), dict)
                else 3
            )
            # Many tools inherit from BaseTool and expose _execute_with_retry
            if hasattr(tool, "_execute_with_retry"):
                return await tool._execute_with_retry(max_attempts=max_attempts, **args)  # type: ignore[attr-defined]
            # Fallback if a custom tool lacks the helper
            return await tool.execute(**args)

        try:
            if timeout_seconds and timeout_seconds > 0:
                result = await asyncio.wait_for(
                    self.error_handler.execute_with_retry(_run_tool),
                    timeout=timeout_seconds,
                )
            else:
                result = await self.error_handler.execute_with_retry(_run_tool)

            # Cache successful results only
            if getattr(result, "success", False):
                self.idempotency_cache.set(idem_key, result)

            # Redact PII in result for logging only
            log_business_event(
                "tool_completed",
                tool=tool_name,
                job_id=job_id,
                success=bool(getattr(result, "success", False)),
            )
            return result

        except asyncio.TimeoutError as te:
            record_error("toolbelt", "timeout", is_critical=False)
            log_error(te, component="toolbelt", tool=tool_name, job_id=job_id)
            return ToolResult(success=False, error=f"Tool '{tool_name}' timed out after {timeout_seconds}s")
        except Exception as e:
            record_error("toolbelt", type(e).__name__, is_critical=False)
            log_error(e, component="toolbelt", tool=tool_name, job_id=job_id)
            return ToolResult(success=False, error=str(e), metadata={"tool": tool_name})
