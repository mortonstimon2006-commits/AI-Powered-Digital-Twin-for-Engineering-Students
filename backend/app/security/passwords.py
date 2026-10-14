"""Argon2id password hashing (argon2-cffi) and password policy (NIST SP 800-63B style:
length over composition rules, block obvious/common choices, no forced rotation)."""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# OWASP-recommended Argon2id baseline: m=19 MiB, t=2, p=1 is the documented minimum; we use
# a stronger memory cost. Tune with `python -m app.cli bench-argon2` on production hardware.
_hasher = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=2, hash_len=32, salt_len=16)

# Pre-computed hash of a random string: verifying against it equalises timing when the
# account does not exist, so response time does not reveal registered emails.
_DUMMY_HASH = _hasher.hash("twinpath-timing-equaliser-not-a-password")

MIN_LENGTH = 12
MAX_LENGTH = 128

# Small embedded blocklist of the most common choices. A production deployment should add a
# larger breached-password list (see docs/security/threat-model.md, "Credential stuffing").
_COMMON = {
    "password",
    "password1",
    "password123",
    "123456789012",
    "qwertyuiop",
    "letmein",
    "welcome",
    "iloveyou",
    "admin",
    "administrator",
    "passw0rd",
    "changeme",
    "abc123",
    "111111111111",
    "qwerty123456",
    "1q2w3e4r5t6y",
    "twinpath",
    "student",
    "engineering",
    "computer",
}


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def password_problems(password: str, *, email: str | None = None, display_name: str | None = None) -> list[str]:
    problems: list[str] = []
    if len(password) < MIN_LENGTH:
        problems.append(f"Use at least {MIN_LENGTH} characters.")
    if len(password) > MAX_LENGTH:
        problems.append(f"Use at most {MAX_LENGTH} characters.")
    lowered = password.lower()
    normalised = "".join(ch for ch in lowered if ch.isalnum())
    if lowered in _COMMON or normalised in _COMMON or any(lowered.startswith(c) and len(lowered) - len(c) <= 3 for c in _COMMON):
        problems.append("This password is too common.")
    if len(set(password)) <= 3:
        problems.append("Avoid repeating the same few characters.")
    if email:
        local = email.split("@", 1)[0].lower()
        if len(local) >= 4 and local in lowered:
            problems.append("Do not include your email address.")
    if display_name and len(display_name) >= 4 and display_name.lower().replace(" ", "") in lowered.replace(" ", ""):
        problems.append("Do not include your name.")
    return problems
