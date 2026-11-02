from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

REQUEST_ID_HEADER = "X-Request-ID"


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized request bodies before they reach route handlers."""

    def __init__(self, app: ASGIApp, max_bytes: int):
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                size = int(content_length)
            except ValueError:
                size = None
            if size is not None and size > self.max_bytes:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "payload_too_large",
                            "message": "Request body exceeds the maximum allowed size.",
                            "context": {"max_bytes": self.max_bytes, "actual_bytes": size},
                        }
                    },
                )
        return await call_next(request)


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


def add_middleware(app: ASGIApp, *, max_request_bytes: int = 1_048_576) -> None:
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=max_request_bytes)
    app.add_middleware(RequestIdMiddleware)
