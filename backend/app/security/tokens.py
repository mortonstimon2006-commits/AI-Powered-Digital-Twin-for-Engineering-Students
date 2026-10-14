"""Opaque random tokens and keyed digests. Only digests are persisted."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import secrets

from app.config import get_settings


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def digest(token: str) -> bytes:
    """SHA-256 of a high-entropy random token (no salt needed: 256-bit random input)."""
    return hashlib.sha256(token.encode("utf-8")).digest()


def keyed_digest(value: str, purpose: str) -> str:
    """HMAC for pseudonymous keys (rate-limit buckets, audit references)."""
    key = get_settings().secret_key.get_secret_value().encode()
    return hmac.new(key, f"{purpose}:{value}".encode(), hashlib.sha256).hexdigest()[:32]


def constant_time_equals(a: bytes, b: bytes) -> bool:
    return hmac.compare_digest(a, b)


def ip_prefix(ip: str | None) -> str | None:
    """Data minimisation: keep only the network prefix (/24 IPv4, /48 IPv6)."""
    if not ip:
        return None
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    prefix = 24 if addr.version == 4 else 48
    return str(ipaddress.ip_network(f"{ip}/{prefix}", strict=False))
