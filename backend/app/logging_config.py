"""Structured JSON logging with defensive redaction.

Rules: never log passwords, tokens, cookies, authorization headers, resumes or chat text.
Callers pass structured `extra={"ctx": {...}}`; keys that look sensitive are masked here as
a second line of defence.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

SENSITIVE_KEY = re.compile(
    r"pass(word)?|secret|token|cookie|authorization|csrf|api[_-]?key|session|otp|mfa|resume|content|prompt",
    re.IGNORECASE,
)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def redact(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return "[depth-limit]"
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if SENSITIVE_KEY.search(str(k)) else redact(v, depth + 1)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [redact(v, depth + 1) for v in value[:20]]
    if isinstance(value, str):
        return EMAIL_RE.sub("[email]", value)[:500]
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": EMAIL_RE.sub("[email]", record.getMessage()),
        }
        ctx = getattr(record, "ctx", None)
        if ctx:
            payload["ctx"] = redact(ctx)
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info and record.exc_info[0] is not None:
            # Exception type + message only; full tracebacks are emitted at DEBUG in dev.
            payload["exc"] = f"{record.exc_info[0].__name__}: {EMAIL_RE.sub('[email]', str(record.exc_info[1]))[:300]}"
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                payload["trace"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    # Uvicorn's access log records full URLs (query strings may hold tokens) — we emit our own.
    logging.getLogger("uvicorn.access").disabled = True
    for noisy in ("httpx", "httpcore", "chromadb", "urllib3", "matplotlib", "posthog"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
