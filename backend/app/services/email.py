"""Transactional email. `file` backend writes .eml files to DATA_DIR/outbox for local
development (rejected by config validation in staging/production); `smtp` uses STARTTLS."""

from __future__ import annotations

import logging
import smtplib
import ssl
from datetime import UTC, datetime
from email.message import EmailMessage

from app.config import EmailBackend, get_settings

log = logging.getLogger("twinpath.email")


def email_enabled() -> bool:
    return get_settings().email_backend != EmailBackend.none


def send_email(to: str, subject: str, body: str) -> bool:
    s = get_settings()
    if s.email_backend == EmailBackend.none:
        return False
    msg = EmailMessage()
    msg["From"] = s.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        if s.email_backend == EmailBackend.file:
            outbox = s.data_dir / "outbox"
            outbox.mkdir(parents=True, exist_ok=True)
            name = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f") + ".eml"
            (outbox / name).write_bytes(bytes(msg))
        else:
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                if s.smtp_username:
                    smtp.login(s.smtp_username, s.smtp_password.get_secret_value())
                smtp.send_message(msg)
        return True
    except Exception:
        log.exception("email delivery failed", extra={"ctx": {"subject": subject}})
        return False


def verification_email(to: str, token: str) -> bool:
    link = f"{get_settings().public_app_url}/verify-email#token={token}"
    return send_email(
        to,
        "Verify your TwinPath AI email address",
        "Confirm your email address for TwinPath AI by opening this link (valid for 24 hours):\n\n"
        f"{link}\n\nIf you did not create an account, you can ignore this message.",
    )


def account_exists_email(to: str) -> bool:
    return send_email(
        to,
        "TwinPath AI registration attempt",
        "Someone tried to register a TwinPath AI account with this email address, but an account "
        "already exists. If this was you, sign in or use 'Forgot password'. Otherwise no action is needed.",
    )


def password_reset_email(to: str, token: str) -> bool:
    link = f"{get_settings().public_app_url}/reset-password#token={token}"
    return send_email(
        to,
        "Reset your TwinPath AI password",
        "A password reset was requested for your TwinPath AI account. This link is valid for 30 minutes "
        f"and can be used once:\n\n{link}\n\nIf you did not request this, ignore this email; your password "
        "has not changed.",
    )


def password_changed_email(to: str) -> bool:
    return send_email(
        to,
        "Your TwinPath AI password was changed",
        "Your TwinPath AI password was just changed and other sessions were signed out. "
        "If this was not you, reset your password immediately and contact your administrator.",
    )
