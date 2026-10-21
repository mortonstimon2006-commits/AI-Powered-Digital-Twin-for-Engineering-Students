"""Smoke test for a running AI Career Guidance App deployment.

A throwaway account walks the core journey (register, log in, onboard, readiness, skill gaps,
roadmap, feedback) and is then permanently deleted. Run it after every deployment:

    uv run python scripts/smoke_hosted.py https://your-app.vercel.app

Optional second argument: the Origin header to send, if it differs from the base URL (for
example when calling the API container directly). Only run it against deployments you operate.
"""

from __future__ import annotations

import secrets
import sys
import time
from typing import Any

import httpx


class Client:
    def __init__(self, base: str, origin: str) -> None:
        self.base = base.rstrip("/")
        self.origin = origin.rstrip("/")
        self.cookies: dict[str, str] = {}
        # Generous timeout: a free-tier backend may need a minute or more to wake up.
        self.http = httpx.Client(timeout=180.0, follow_redirects=False)

    def call(self, method: str, path: str, expect: tuple[int, ...] = (200,), **kw: Any) -> httpx.Response:
        # Cookies are handled by hand so `Secure` / `__Host-` cookies also work against
        # http://localhost test stacks, exactly as a browser treats localhost.
        headers = {"X-Requested-With": "twinpath", "Origin": self.origin, "Accept": "application/json"}
        if self.cookies:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        csrf = next((v for k, v in self.cookies.items() if k.endswith("tp_csrf")), None)
        if csrf:
            headers["X-CSRF-Token"] = csrf
        started = time.monotonic()
        resp = self.http.request(method, self.base + path, headers=headers, **kw)
        for raw in resp.headers.get_list("set-cookie"):
            name, _, rest = raw.partition("=")
            value = rest.split(";", 1)[0]
            if value and "max-age=0" not in raw.lower():
                self.cookies[name.strip()] = value
            else:
                self.cookies.pop(name.strip(), None)
        took = time.monotonic() - started
        ok = resp.status_code in expect
        print(f"{'ok ' if ok else 'FAIL'} {resp.status_code} {took:6.2f}s {method} {path}")
        if not ok:
            print("     " + resp.text[:300])
            raise SystemExit(1)
        return resp


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    c = Client(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else sys.argv[1])
    ready = c.call("GET", "/api/v1/health/ready").json()
    print(f"     health: {ready}")

    email = f"smoke.{secrets.token_hex(6)}@example.edu"
    password = secrets.token_urlsafe(18)
    c.call(
        "POST",
        "/api/v1/auth/register",
        expect=(200, 201, 202),
        json={"email": email, "password": password, "display_name": "Smoke Test", "accept_profile_processing": True},
    )
    login = c.call("POST", "/api/v1/auth/login", json={"email": email, "password": password}).json()
    if login.get("status") != "authenticated":
        raise SystemExit(f"login did not authenticate: {login.get('status')}")
    try:
        roles = c.call("GET", "/api/v1/roles").json()["roles"]
        c.call("PUT", "/api/v1/profile/roles", json={"target_role_id": roles[0]["id"]})
        c.call("POST", "/api/v1/profile/onboarding/complete")
        me = c.call("GET", "/api/v1/auth/me").json()
        assert me["onboarding_completed"], "onboarding not recorded"
        readiness = c.call("POST", "/api/v1/readiness/analyse").json()
        print(f"     readiness model available: {readiness.get('available')}")
        c.call("GET", "/api/v1/skill-gaps/summary")
        c.call("POST", "/api/v1/roadmaps/generate", expect=(200, 201), json={})
        resume = (
            b"Smoke Test\nComputer engineering student\nSkills: Python, SQL, Git, Docker, React\n"
            b"Projects: built a REST API with FastAPI and PostgreSQL and deployed it with Docker.\n"
        )
        doc = c.call(
            "POST",
            "/api/v1/documents",
            expect=(201,),
            files={"file": ("resume.txt", resume, "text/plain")},
            data={"kind": "resume"},
        ).json()
        print(f"     resume parsed: status={doc.get('status')}")
        c.call("POST", "/api/v1/feedback", json={"target_type": "general", "rating": 5, "comment": "automated smoke test"})
        mentor = c.call("GET", "/api/v1/mentor/status").json()
        print(f"     mentor status: {mentor}")
    finally:
        c.call(
            "POST",
            "/api/v1/privacy/delete-account",
            json={"password": password, "confirmation": "DELETE MY ACCOUNT"},
        )
    print("smoke test passed; the test account was deleted")


if __name__ == "__main__":
    main()
