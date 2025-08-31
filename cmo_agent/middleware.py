from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from .obs.logging import log, with_request_context
import time


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # noqa: D401
        with_request_context(request)
        start = time.perf_counter()
        try:
            log.info("http_req", evt="http_req", method=request.method, path=request.url.path)
            response: Response = await call_next(request)
            return response
        finally:
            dur_ms = int((time.perf_counter() - start) * 1000)
            status = 0
            try:
                status = int(getattr(response, "status_code", 0))  # type: ignore[name-defined]
            except Exception:
                pass
            log.info("http_res", evt="http_res", status=status, path=request.url.path, latency_ms=dur_ms)


