"""Sliding-window rate limiter.

The in-process backend is correct for a single API process (the supported pilot topology:
one uvicorn worker behind a reverse proxy). Running several workers/replicas requires a
shared backend (e.g. Redis) — see docs/deployment.md; until then each process enforces its
own window, which weakens but does not remove the protection.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

from app.errors import TooManyRequests
from app.security.tokens import keyed_digest


@dataclass(frozen=True)
class Limit:
    name: str
    max_events: int
    window_seconds: int


class SlidingWindowLimiter:
    def __init__(self, max_keys: int = 50_000) -> None:
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._max_keys = max_keys

    def hit(self, limit: Limit, key: str) -> None:
        bucket = f"{limit.name}:{keyed_digest(key, 'ratelimit')}"
        now = time.monotonic()
        with self._lock:
            q = self._events.get(bucket)
            if q is None:
                if len(self._events) >= self._max_keys:
                    self._evict(now)
                q = self._events.setdefault(bucket, deque())
            while q and now - q[0] > limit.window_seconds:
                q.popleft()
            if len(q) >= limit.max_events:
                retry = int(limit.window_seconds - (now - q[0])) + 1
                raise TooManyRequests(retry_after=max(retry, 1))
            q.append(now)

    def _evict(self, now: float) -> None:
        horizon = 3600
        for k in [k for k, q in self._events.items() if not q or now - q[-1] > horizon]:
            del self._events[k]

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


limiter = SlidingWindowLimiter()

LOGIN_IP = Limit("login_ip", 20, 300)
LOGIN_ACCOUNT = Limit("login_account", 8, 300)
REGISTER_IP = Limit("register_ip", 10, 3600)
RESET_REQUEST_IP = Limit("reset_ip", 10, 3600)
RESET_REQUEST_ACCOUNT = Limit("reset_account", 3, 3600)
TOKEN_REDEEM_IP = Limit("token_redeem_ip", 20, 900)
MENTOR_USER = Limit("mentor_user", 20, 600)
UPLOAD_USER = Limit("upload_user", 20, 3600)
SIMULATION_USER = Limit("simulation_user", 120, 600)
EXPENSIVE_USER = Limit("expensive_user", 60, 600)
FEEDBACK_USER = Limit("feedback_user", 30, 3600)
