from __future__ import annotations

import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from backend.src.utils.logging import get_logger, log_event

logger = get_logger(__name__)


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        started = time.perf_counter()
        request_id = (
            request.headers.get("x-request-id")
            or request.headers.get("x-correlation-id")
            or uuid4().hex[:16]
        )
        request.state.request_id = request_id

        response = await call_next(request)

        latency_ms = int((time.perf_counter() - started) * 1000)
        user_id = str(getattr(request.state, "user_id", "anon"))
        log_event(
            logger,
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=latency_ms,
            request_id=request_id,
            user_id=user_id,
        )
        response.headers["x-request-id"] = request_id
        response.headers["x-response-time-ms"] = str(latency_ms)
        return response
