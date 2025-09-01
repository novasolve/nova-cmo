import logging
import sys
import uuid
import re
import os
from typing import Optional


# Attempt to use structlog if available; otherwise fall back to stdlib JSON-ish logging
try:
    import structlog  # type: ignore
    from structlog.contextvars import bind_contextvars, clear_contextvars  # type: ignore
    from structlog.processors import JSONRenderer, TimeStamper  # type: ignore
    from structlog.stdlib import add_log_level, filter_by_level  # type: ignore
    _HAS_STRUCTLOG = True
except Exception:  # pragma: no cover - safe fallback
    structlog = None  # type: ignore
    bind_contextvars = clear_contextvars = None  # type: ignore
    JSONRenderer = TimeStamper = add_log_level = filter_by_level = None  # type: ignore
    _HAS_STRUCTLOG = False


SILENT_PATHS = [
    re.compile(r"^/api/jobs$"),
    re.compile(r"^/api/jobs/.+/events$"),
    re.compile(r"^/threads/.+/messages$"),
]


class PathFilter(logging.Filter):
    """Suppress noisy uvicorn access logs for known chat/SSE polling paths."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        try:
            # Uvicorn access logger uses record.msg like '"GET /path HTTP/1.1" 200 OK'
            msg = record.getMessage() if hasattr(record, "getMessage") else getattr(record, "msg", "")
            if record.name.startswith("uvicorn.access") and isinstance(msg, str):
                # Extract the path if present
                m = re.search(r"\s(\/[^\s]*)\sHTTP\/", msg)
                path = m.group(1) if m else ""
                for pat in SILENT_PATHS:
                    if pat.search(path):
                        return False
        except Exception:
            # Never block logs on filter failure
            return True
        return True


def configure_logging(level: str = "INFO") -> None:
    """Configure process-wide structured logging.

    Uses structlog when available; otherwise configures stdlib logging.
    """
    root = logging.getLogger()
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(PathFilter())

    # PII-safe email masker; allow override via LOG_PII=allow
    EMAIL_RE = re.compile(r"([A-Z0-9._%+-]+)@([A-Z0-9.-]+\.[A-Z]{2,})", re.IGNORECASE)
    ALLOW_PII = os.getenv("LOG_PII", "deny").lower() == "allow"

    def _mask_emails(value: str) -> str:
        if ALLOW_PII or not isinstance(value, str):
            return value
        def repl(m):
            user = m.group(1)
            domain = m.group(2)
            if "noreply" in user.lower():
                return f"{user}@{domain}"
            if len(user) <= 2:
                return "***@" + domain
            return user[0] + "***@" + domain
        return EMAIL_RE.sub(repl, value)

    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            import json
            from datetime import datetime

            log_event = {
                "ts": datetime.utcnow().isoformat(),
                "level": record.levelname,
            }
            # If structured data was passed via extra:
            structured = getattr(record, "structured", None)
            if structured and isinstance(structured, dict):
                # Merge structured keys (like event, jobId, etc.)
                log_event.update(structured)
                # Apply PII masking to structured fields
                for k in list(log_event.keys()):
                    v = log_event[k]
                    if isinstance(v, str):
                        log_event[k] = _mask_emails(v)
                    elif isinstance(v, (list, tuple)):
                        log_event[k] = [_mask_emails(x) if isinstance(x, str) else x for x in v]
                # Redact secrets
                for k in list(log_event.keys()):
                    lk = k.lower()
                    if "key" in lk or "token" in lk or "secret" in lk:
                        log_event[k] = "***"
            else:
                # Fallback to the raw message with PII masking
                log_event["message"] = _mask_emails(record.getMessage())
            return json.dumps(log_event)

    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def with_request_context(req, thread_id: Optional[str] = None) -> None:
    """Bind request-level correlation IDs to the context."""
    if _HAS_STRUCTLOG and bind_contextvars is not None and clear_contextvars is not None:
        clear_contextvars()
        bind_contextvars(
            reqId=req.headers.get("x-request-id", str(uuid.uuid4())),
            threadId=thread_id,
        )


def with_job_context(thread_id: Optional[str], job_id: Optional[str]) -> None:
    if _HAS_STRUCTLOG and bind_contextvars is not None and clear_contextvars is not None:
        clear_contextvars()
        bind_contextvars(threadId=thread_id, jobId=job_id)


if _HAS_STRUCTLOG:
    log = structlog.get_logger("cmo")  # type: ignore
else:
    # Provide a shim logger that accepts **kwargs and stores them on record for formatter
    class _ShimLogger(logging.LoggerAdapter):
        def process(self, msg, kwargs):  # noqa: D401
            extra = kwargs.pop("extra", {})
            if "_extra" in kwargs:
                extra.update(kwargs.pop("_extra"))
            kwargs["extra"] = {"_extra": extra}
            return msg, kwargs

        def info(self, msg, **kwargs):
            super().info(msg, extra=kwargs)

        def warning(self, msg, **kwargs):
            super().warning(msg, extra=kwargs)

        def error(self, msg, **kwargs):
            super().error(msg, extra=kwargs)

    log = _ShimLogger(logging.getLogger("cmo"), {})
