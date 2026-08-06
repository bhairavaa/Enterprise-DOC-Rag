import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.logging import get_logger, new_request_id, request_id_var

logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns a request id (correlates logs with Phoenix traces) and logs
    each request's outcome/latency."""

    async def dispatch(self, request: Request, call_next):
        req_id = new_request_id()
        token = request_id_var.set(req_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("request_failed", path=request.url.path, method=request.method)
            raise
        finally:
            request_id_var.reset(token)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = req_id
        logger.info(
            "request_completed",
            path=request.url.path,
            method=request.method,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response
