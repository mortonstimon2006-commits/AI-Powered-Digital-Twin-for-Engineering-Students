"""Field-level encryption for small secrets (TOTP seeds) using Fernet (AES-128-CBC +
HMAC-SHA256, from the `cryptography` package). The key lives in the environment / a secret
manager, never in the database, so a DB dump alone cannot reveal MFA seeds."""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    return Fernet(get_settings().field_encryption_key.get_secret_value().encode())


def encrypt(plaintext: str) -> bytes:
    return _fernet().encrypt(plaintext.encode("utf-8"))


def decrypt(ciphertext: bytes) -> str | None:
    try:
        return _fernet().decrypt(ciphertext).decode("utf-8")
    except InvalidToken:
        return None
