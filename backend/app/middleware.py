"""ASGI middleware: request IDs + access log, request-body size limit, security headers,
and a browser-request guard (custom header + Origin allow-list) that blocks CSRF on
endpoints that run before a session exists (login, register, password reset)."""

from __future__ import annotations

import logging
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import get_settings

access_log = logging.getLogger("twinpath.access")

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

_API_HEADERS = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"cross-origin-opener-policy", b"same-origin"),
    (b"cross-origin-resource-policy", b"same-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
    # Personal data must never be stored by shared caches or the browser cache.
    (b"cache-control", b"no-store"),
]
_API_CSP = (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'; base-uri 'none'")


async def _send_json_error(send: Send, status: int, code: str, message: str, request_id: str) -> None:
    import json

    body = json.dumps({"error": {"code": code, "message": message, "request_id": request_id}}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"x-request-id", request_id.encode()),
                *_API_HEADERS,
                _API_CSP,
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class SecurityMiddleware:
    def __init__(self, app: ASGIApp, max_body_bytes: int) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes
        settings = get_settings()
        self.allowed_origins = set(settings.origins)
        self.hsts = settings.is_production_like

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        method: str = scope["method"]
        path: str = scope["path"]
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        started = time.perf_counter()
        status_holder = {"status": 500}

        # --- browser-request guard for state-changing API calls ---
        if method in UNSAFE_METHODS and path.startswith("/api/"):
            origin = headers.get("origin")
            if origin is not None and origin.rstrip("/") not in self.allowed_origins:
                await _send_json_error(send, 403, "origin_rejected", "Cross-origin request rejected.", request_id)
                self._log(method, path, 403, started, request_id)
                return
            if headers.get("x-requested-with") != "twinpath":
                await _send_json_error(send, 403, "csrf_header_missing", "Missing anti-CSRF request header.", request_id)
                self._log(method, path, 403, started, request_id)
                return

        # --- request size limit (declared and streamed) ---
        declared = headers.get("content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.max_body_bytes:
            await _send_json_error(send, 413, "payload_too_large", "Request body is too large.", request_id)
            self._log(method, path, 413, started, request_id)
            return

        received = 0
        too_large = False

        async def limited_receive() -> Message:
            nonlocal received, too_large
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_body_bytes:
                    too_large = True
                    raise _BodyTooLarge
            return message

        is_docs = path.startswith(("/api/docs", "/api/redoc", "/api/openapi.json"))

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                hdrs = list(message.get("headers", []))
                existing = {k.lower() for k, _ in hdrs}
                for k, v in _API_HEADERS:
                    if k not in existing:
                        hdrs.append((k, v))
                if not is_docs and b"content-security-policy" not in existing:
                    hdrs.append(_API_CSP)
                if self.hsts:
                    hdrs.append((b"strict-transport-security", b"max-age=63072000; includeSubDomains"))
                hdrs.append((b"x-request-id", request_id.encode()))
                message["headers"] = hdrs
            await send(message)

        try:
            await self.app(scope, limited_receive, send_with_headers)
        except _BodyTooLarge:
            if too_large:
                await _send_json_error(send, 413, "payload_too_large", "Request body is too large.", request_id)
                status_holder["status"] = 413
        finally:
            self._log(method, path, status_holder["status"], started, request_id)

    @staticmethod
    def _log(method: str, path: str, status: int, started: float, request_id: str) -> None:
        access_log.info(
            "request",
            extra={
                "request_id": request_id,
                "ctx": {"method": method, "path": path, "status": status, "ms": round((time.perf_counter() - started) * 1000, 1)},
            },
        )


class _BodyTooLarge(Exception):
    pass
