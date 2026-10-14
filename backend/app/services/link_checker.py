"""Validates learning-resource URLs before they are presented as 'verified'.

SSRF guard: only https URLs; every hop's hostname is resolved and rejected if it maps to a
private, loopback, link-local, multicast or reserved address; redirects are followed manually
(max 5) so each hop is re-checked. Bot-protection responses (401/403/429/5xx) are recorded
as 'unverified', never as 'verified' and never as 'broken'.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urljoin, urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LearningResource

USER_AGENT = "TwinPathLinkChecker/0.1 (+resource verification; contact: administrator)"
MAX_REDIRECTS = 5


class UnsafeUrl(ValueError):
    pass


def assert_public_https(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise UnsafeUrl("only https URLs with a hostname are allowed")
    if parts.username or parts.password:
        raise UnsafeUrl("credentials in URLs are not allowed")
    try:
        infos = socket.getaddrinfo(parts.hostname, parts.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeUrl("hostname does not resolve") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global or ip.is_multicast:
            raise UnsafeUrl("URL resolves to a non-public address")


@dataclass
class CheckResult:
    status: str  # verified | broken | unverified
    http_status: int | None
    final_url: str | None
    note: str


def check_url(url: str, timeout: float = 10.0) -> CheckResult:
    current = url
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False, headers={"User-Agent": USER_AGENT}) as client:
            for _ in range(MAX_REDIRECTS + 1):
                assert_public_https(current)
                resp = client.get(current)
                if resp.is_redirect and "location" in resp.headers:
                    current = urljoin(current, resp.headers["location"])
                    continue
                code = resp.status_code
                if 200 <= code < 300:
                    return CheckResult("verified", code, current, "reachable")
                if code in (404, 410):
                    return CheckResult("broken", code, current, "not found")
                return CheckResult("unverified", code, current, "server refused automated check")
            return CheckResult("unverified", None, current, "too many redirects")
    except UnsafeUrl as exc:
        return CheckResult("broken", None, current, f"unsafe: {exc}")
    except httpx.HTTPError as exc:
        return CheckResult("unverified", None, current, f"network error: {type(exc).__name__}")


def validate_resources(db: Session, resource_ids: list[int] | None = None) -> list[dict[str, object]]:
    stmt = select(LearningResource)
    if resource_ids:
        stmt = stmt.where(LearningResource.id.in_(resource_ids))
    report = []
    for res in db.scalars(stmt):
        result = check_url(res.url)
        res.verification_status = result.status
        res.last_http_status = result.http_status
        res.last_checked_at = datetime.now(UTC)
        report.append(
            {
                "id": res.id,
                "title": res.title,
                "url": res.url,
                "status": result.status,
                "http_status": result.http_status,
                "final_url": result.final_url,
                "note": result.note,
            }
        )
    db.flush()
    return report
