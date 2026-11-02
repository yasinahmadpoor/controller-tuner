from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import DomainError
from app.core.logging import get_logger

logger = get_logger(__name__)


def _validation_context(exc: RequestValidationError) -> list[dict[str, Any]]:
    return [
        {"location": list(error.get("loc", [])), "message": error.get("msg", "")}
        for error in exc.errors()
    ]


def _http_body_code(exc: StarletteHTTPException) -> str | None:
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        return str(exc.detail["code"])
    return None


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def handle_domain_error(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.as_codec())

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        logger.debug("payload rejected", errors=exc.errors())
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request payload failed schema validation.",
                    "context": {"errors": _validation_context(exc)},
                }
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _http_body_code(exc)
        if code is not None:
            message = (
                exc.detail.get("message", exc.detail["code"])
                if isinstance(exc.detail, dict)
                else None
            )
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": {
                        "code": code,
                        "message": message or code.replace("_", " "),
                        "context": {},
                    }
                },
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": "http_error",
                    "message": str(exc.detail),
                    "context": {},
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_uncaught_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled exception", path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "Internal server error.",
                    "context": {},
                }
            },
        )
