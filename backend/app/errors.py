"""Uniform error envelope: {"error": {"code", "message", "details"?, "request_id"}}.

Internal exceptions are logged server-side and returned as a generic 500 — no stack
traces, SQL, file paths or configuration ever reach the client.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("twinpath.errors")


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, details: Any = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code
        self.details = details


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthenticated"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class TooManyRequests(AppError):
    status_code = 429
    code = "rate_limited"

    def __init__(self, message: str = "Too many requests. Please slow down.", retry_after: int = 60):
        super().__init__(message)
        self.retry_after = retry_after


class ServiceUnavailable(AppError):
    status_code = 503
    code = "service_unavailable"


def _envelope(
    request: Request, status: int, code: str, message: str, details: Any = None, headers: dict[str, str] | None = None
) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": message, "request_id": getattr(request.state, "request_id", None)}
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status, content={"error": body}, headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        headers = {"Retry-After": str(exc.retry_after)} if isinstance(exc, TooManyRequests) else None
        return _envelope(request, exc.status_code, exc.code, exc.message, exc.details, headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(p) for p in err.get("loc", ())[1:]) or None,
                "message": err.get("msg", "invalid"),
                "type": err.get("type"),
            }
            for err in exc.errors()
        ]
        return _envelope(request, 422, "validation_error", "The request contains invalid fields.", details)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed", 413: "payload_too_large"}.get(exc.status_code, "http_error")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return _envelope(request, exc.status_code, code, message)

    @app.exception_handler(IntegrityError)
    async def _integrity(request: Request, exc: IntegrityError) -> JSONResponse:
        log.warning(
            "integrity error", extra={"ctx": {"constraint": getattr(getattr(exc.orig, "diag", None), "constraint_name", None)}}
        )
        return _envelope(request, 409, "conflict", "The request conflicts with existing data.")

    @app.exception_handler(OperationalError)
    async def _db_down(request: Request, exc: OperationalError) -> JSONResponse:
        log.error("database operational error", exc_info=exc)
        return _envelope(request, 503, "database_unavailable", "The database is temporarily unavailable.")

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled error", exc_info=exc, extra={"request_id": getattr(request.state, "request_id", None)})
        return _envelope(request, 500, "internal_error", "An unexpected error occurred.")
