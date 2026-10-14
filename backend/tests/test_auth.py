from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pyotp
from sqlalchemy import text

from tests.conftest import STRONG_PASSWORD, login, outbox_tokens, register

API = "/api/v1/auth"


def test_register_is_non_enumerating_and_sends_mail(client):
    r1 = client.post(
        f"{API}/register",
        json={
            "email": "Asha@Example.edu",
            "password": STRONG_PASSWORD,
            "display_name": "Asha",
            "accept_profile_processing": True,
        },
    )
    r2 = client.post(
        f"{API}/register",
        json={
            "email": "asha@example.edu",
            "password": STRONG_PASSWORD,
            "display_name": "Someone",
            "accept_profile_processing": True,
        },
    )
    assert r1.status_code == r2.status_code == 202
    assert r1.json() == r2.json()  # identical response whether or not the account existed
    assert len(outbox_tokens("verify-email")) == 1  # second attempt got an "account exists" mail instead


def test_weak_password_and_missing_consent_rejected(client):
    r = client.post(
        f"{API}/register",
        json={"email": "b@example.edu", "password": "password1234", "display_name": "B", "accept_profile_processing": True},
    )
    assert r.status_code == 422
    r = client.post(
        f"{API}/register",
        json={"email": "b@example.edu", "password": "short", "display_name": "Bea", "accept_profile_processing": True},
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "weak_password"
    r = client.post(
        f"{API}/register",
        json={"email": "b@example.edu", "password": STRONG_PASSWORD, "display_name": "Bea", "accept_profile_processing": False},
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "consent_required"


def test_unknown_fields_rejected(client):
    r = client.post(
        f"{API}/register",
        json={
            "email": "c@example.edu",
            "password": STRONG_PASSWORD,
            "display_name": "C",
            "accept_profile_processing": True,
            "role": "admin",
        },
    )
    assert r.status_code == 422


def test_login_errors_do_not_reveal_account_existence(client):
    register(client, "d@example.edu")
    wrong = client.post(f"{API}/login", json={"email": "d@example.edu", "password": "wrong-password-123"})
    missing = client.post(f"{API}/login", json={"email": "nobody@example.edu", "password": "wrong-password-123"})
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json()["error"]["message"] == missing.json()["error"]["message"]
    assert wrong.json()["error"]["code"] == missing.json()["error"]["code"]


def test_login_sets_hardened_cookies_and_me_works(client):
    register(client, "e@example.edu")
    r = client.post(f"{API}/login", json={"email": "e@example.edu", "password": STRONG_PASSWORD})
    assert r.status_code == 200
    set_cookie = r.headers.get_list("set-cookie")
    session_cookie = next(c for c in set_cookie if c.startswith("tp_session="))
    assert "HttpOnly" in session_cookie and "SameSite=lax" in session_cookie
    csrf_cookie = next(c for c in set_cookie if c.startswith("tp_csrf="))
    assert "HttpOnly" not in csrf_cookie
    me = client.get(f"{API}/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "e@example.edu"
    assert me.json()["user"]["role"] == "student"


def test_credentials_are_stored_only_as_hashes(client, owner_engine):
    register(client, "f@example.edu")
    login(client, "f@example.edu")
    with owner_engine.connect() as conn:
        pw_hash = conn.execute(text("SELECT password_hash FROM users WHERE email='f@example.edu'")).scalar_one()
        token_hash = conn.execute(text("SELECT token_hash FROM user_sessions")).scalar_one()
    assert pw_hash.startswith("$argon2id$") and STRONG_PASSWORD not in pw_hash
    assert client.cookies.get("tp_session").encode() != bytes(token_hash)
    assert len(bytes(token_hash)) == 32


def test_csrf_and_origin_protections(client):
    register(client, "g@example.edu")
    login(client, "g@example.edu")
    # Missing CSRF token on an authenticated state-changing request.
    r = client.post(f"{API}/sessions/revoke-others", headers={"X-CSRF-Token": "forged-token-value-xxxxxxxxx"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_invalid"
    # Missing custom header (what a cross-site HTML form would send).
    r = client.post(
        f"{API}/login", json={"email": "g@example.edu", "password": STRONG_PASSWORD}, headers={"X-Requested-With": ""}
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "csrf_header_missing"
    # Disallowed Origin.
    r = client.post(
        f"{API}/login", json={"email": "g@example.edu", "password": STRONG_PASSWORD}, headers={"Origin": "https://evil.example"}
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "origin_rejected"
    # Valid token works.
    r = client.post(f"{API}/sessions/revoke-others")
    assert r.status_code == 200


def test_logout_revokes_session(client):
    register(client, "h@example.edu")
    login(client, "h@example.edu")
    token = client.cookies.get("tp_session")
    assert client.post(f"{API}/logout").status_code == 200
    client.cookies.set("tp_session", token)  # replaying the old cookie must not work
    assert client.get(f"{API}/me").status_code == 401


def test_lockout_after_repeated_failures(client, owner_engine):
    register(client, "i@example.edu")
    for _ in range(5):
        assert client.post(f"{API}/login", json={"email": "i@example.edu", "password": "nope-nope-nope"}).status_code == 401
    # Correct password is refused while locked, with the same generic message.
    r = client.post(f"{API}/login", json={"email": "i@example.edu", "password": STRONG_PASSWORD})
    assert r.status_code == 401
    with owner_engine.connect() as conn:
        locked_until = conn.execute(text("SELECT locked_until FROM users WHERE email='i@example.edu'")).scalar_one()
    assert locked_until > datetime.now(UTC) + timedelta(minutes=10)
    events = []
    with owner_engine.connect() as conn:
        events = conn.execute(text("SELECT outcome FROM audit_events WHERE action='auth.login'")).scalars().all()
    assert events.count("failure") == 5 and "denied" in events


def test_login_rate_limit(client):
    for _ in range(8):
        client.post(f"{API}/login", json={"email": "ratelimited@example.edu", "password": "whatever-123456"})
    r = client.post(f"{API}/login", json={"email": "ratelimited@example.edu", "password": "whatever-123456"})
    assert r.status_code == 429
    assert "retry-after" in {k.lower() for k in r.headers}


def test_password_reset_flow_single_use_and_revokes_sessions(make_client):
    a, b = make_client(), make_client()
    register(a, "j@example.edu")
    login(a, "j@example.edu")
    r = b.post(f"{API}/password/forgot", json={"email": "j@example.edu"})
    r_unknown = b.post(f"{API}/password/forgot", json={"email": "unknown@example.edu"})
    assert r.status_code == r_unknown.status_code == 202 and r.json() == r_unknown.json()
    token = outbox_tokens("reset-password")[-1]
    new_pw = "a-completely-new-passphrase-77"
    assert b.post(f"{API}/password/reset", json={"token": token, "new_password": new_pw}).status_code == 200
    # token is single-use
    again = b.post(f"{API}/password/reset", json={"token": token, "new_password": new_pw + "x"})
    assert again.status_code == 400 and again.json()["error"]["code"] == "token_invalid"
    # existing sessions were revoked
    assert a.get(f"{API}/me").status_code == 401
    assert b.post(f"{API}/login", json={"email": "j@example.edu", "password": STRONG_PASSWORD}).status_code == 401
    login(b, "j@example.edu", new_pw)


def test_expired_reset_token_rejected(client, owner_engine):
    register(client, "k@example.edu")
    client.post(f"{API}/password/forgot", json={"email": "k@example.edu"})
    token = outbox_tokens("reset-password")[-1]
    with owner_engine.begin() as conn:
        conn.execute(text("UPDATE auth_tokens SET expires_at = now() - interval '1 minute' WHERE purpose='reset_password'"))
    r = client.post(f"{API}/password/reset", json={"token": token, "new_password": "another-good-passphrase-1"})
    assert r.status_code == 400


def test_change_password_revokes_other_sessions(make_client):
    a, b = make_client(), make_client()
    register(a, "l@example.edu")
    login(a, "l@example.edu")
    login(b, "l@example.edu")
    r = a.post(f"{API}/password/change", json={"current_password": "bad-current-pass", "new_password": "x" * 20})
    assert r.status_code == 400
    r = a.post(f"{API}/password/change", json={"current_password": STRONG_PASSWORD, "new_password": "fresh-new-passphrase-2026"})
    assert r.status_code == 200
    assert a.get(f"{API}/me").status_code == 200
    assert b.get(f"{API}/me").status_code == 401


def test_sessions_are_owner_scoped(make_client):
    a, b = make_client(), make_client()
    register(a, "m@example.edu")
    register(b, "n@example.edu")
    login(a, "m@example.edu")
    login(b, "n@example.edu")
    b_session_id = b.get(f"{API}/sessions").json()[0]["id"]
    # A cannot revoke B's session by guessing/obtaining its id (IDOR).
    assert a.delete(f"{API}/sessions/{b_session_id}").status_code == 404
    assert b.get(f"{API}/me").status_code == 200


def test_email_verification(client):
    register(client, "o@example.edu")
    login(client, "o@example.edu")
    assert client.get(f"{API}/me").json()["user"]["email_verified"] is False
    token = outbox_tokens("verify-email")[-1]
    assert client.post(f"{API}/email/verify", json={"token": token}).status_code == 200
    assert client.get(f"{API}/me").json()["user"]["email_verified"] is True
    assert client.post(f"{API}/email/verify", json={"token": token}).status_code == 400


def test_mfa_enrolment_login_and_disable(make_client):
    a = make_client()
    register(a, "p@example.edu")
    login(a, "p@example.edu")
    setup = a.post(f"{API}/mfa/setup").json()
    totp = pyotp.TOTP(setup["secret"])
    assert a.post(f"{API}/mfa/verify", json={"code": "000000" if totp.now() != "000000" else "111111"}).status_code == 400
    assert a.post(f"{API}/mfa/verify", json={"code": totp.now()}).status_code == 200

    b = make_client()
    r = b.post(f"{API}/login", json={"email": "p@example.edu", "password": STRONG_PASSWORD})
    assert r.json()["status"] == "mfa_required" and "tp_session" not in b.cookies
    challenge = r.json()["mfa_challenge"]
    bad = b.post(f"{API}/login/mfa", json={"challenge": challenge, "code": "123456" if totp.now() != "123456" else "654321"})
    assert bad.status_code == 401
    ok = b.post(f"{API}/login/mfa", json={"challenge": challenge, "code": totp.now()})
    assert ok.status_code == 200 and ok.json()["status"] == "authenticated"
    assert b.get(f"{API}/me").json()["user"]["mfa_enabled"] is True
    # challenge is single-use
    assert b.post(f"{API}/login/mfa", json={"challenge": challenge, "code": totp.now()}).status_code == 400
    assert b.post(f"{API}/mfa/disable", json={"password": STRONG_PASSWORD, "code": totp.now()}).status_code == 200


def test_security_headers_and_error_envelope(client):
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    body = r.json()["error"]
    assert body["code"] == "not_found" and body["request_id"]
    for header in (
        "x-content-type-options",
        "x-frame-options",
        "content-security-policy",
        "cache-control",
        "referrer-policy",
        "x-request-id",
    ):
        assert header in r.headers
    assert r.headers["cache-control"] == "no-store"


def test_oversized_body_rejected(client):
    r = client.post(f"{API}/login", content=b"x" * (6 * 1024 * 1024), headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_unauthenticated_access_rejected(client):
    assert client.get(f"{API}/me").status_code == 401
    assert client.get(f"{API}/sessions").status_code == 401
