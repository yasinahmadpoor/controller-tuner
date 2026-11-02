from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Inject a request ID into logs and echo it back as a response header."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(
            request_id=request_id, method=request.method, path=request.url.path
        )
        try:
            start = time.perf_counter()
            response = await call_next(request)
        except Exception:
            structlog.get_logger("app.access").error("request failed")
            raise
        else:
            duration_ms = round((time.perf_counter() - start) * 1000, 3)
            structlog.contextvars.bind_contextvars(duration_ms=duration_ms)
            structlog.get_logger("app.access").info(
                "request completed", status=response.status_code
            )
        finally:
            structlog.contextvars.unbind_contextvars("request_id", "method", "path", "duration_ms")
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def add_middleware(app: ASGIApp) -> None:
    app.add_middleware(RequestIdMiddleware)
