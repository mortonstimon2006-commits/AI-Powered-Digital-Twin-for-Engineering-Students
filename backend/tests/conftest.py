"""Test harness. Runs against a REAL PostgreSQL test database (never SQLite) using the same
least-privilege app role as production, so RLS and grants are exercised for real.

Requires the `db` compose service (or CI's Postgres service) and TEST_DATABASE_URL /
TEST_MIGRATION_DATABASE_URL in the environment or the repo-level .env.
"""

from __future__ import annotations

import os
import re
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from dotenv import dotenv_values

REPO = Path(__file__).resolve().parents[2]
_env = {**dotenv_values(REPO / ".env"), **os.environ}
_test_db = _env.get("TEST_DATABASE_URL")
_test_owner_db = _env.get("TEST_MIGRATION_DATABASE_URL")
if not _test_db or not _test_owner_db:
    raise RuntimeError("TEST_DATABASE_URL and TEST_MIGRATION_DATABASE_URL must be set for tests")

_tmp = Path(tempfile.mkdtemp(prefix="twinpath-test-"))
os.environ.update(
    {
        "TWINPATH_ENV": "test",
        "DATABASE_URL": _test_db,
        "MIGRATION_DATABASE_URL": _test_owner_db,
        "COOKIE_SECURE": "false",
        "EMAIL_BACKEND": "file",
        "REQUIRE_EMAIL_VERIFICATION": "false",
        "DATA_DIR": str(_tmp / "var"),
        "MODEL_ARTIFACT_DIR": str(_tmp / "models"),
        "ALLOWED_ORIGINS": "http://localhost:5173",
        "SECRET_KEY": _env.get("SECRET_KEY") or "test-secret-key-test-secret-key-0123456789",
        "FIELD_ENCRYPTION_KEY": _env.get("FIELD_ENCRYPTION_KEY") or "x" * 43 + "=",
    }
)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from app.security.ratelimit import limiter  # noqa: E402

BACKEND = REPO / "backend"


@pytest.fixture(scope="session")
def owner_engine():
    engine = create_engine(_test_owner_db)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def migrated(owner_engine) -> Iterator[None]:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.attributes["url"] = _test_owner_db
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield


def _truncate_all(owner_engine) -> None:
    with owner_engine.begin() as conn:
        tables = (
            conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename <> 'alembic_version'"))
            .scalars()
            .all()
        )
        conn.execute(text("TRUNCATE " + ", ".join(f'"{t}"' for t in tables) + " RESTART IDENTITY CASCADE"))


@pytest.fixture(autouse=True)
def clean_db(owner_engine) -> Iterator[None]:
    _truncate_all(owner_engine)
    limiter.reset()
    from app.ml.registry import registry

    registry._active = None
    yield


@pytest.fixture
def seeded(owner_engine) -> None:
    """Loads the documented reference catalogue (skills, roles, resources, assessments)."""
    from app.db import system_session
    from app.seed.catalogue import seed_catalogue

    with system_session() as db:
        seed_catalogue(db)


@pytest.fixture(scope="session")
def trained_artifact() -> Path:
    """Trains a small model once per test session (quick grids, synthetic data) into the
    temporary artifact directory, so tests never depend on locally trained files."""
    from ml_pipeline.train import train

    return train("synthetic", seed=7, n_students=500, out_dir=Path(os.environ["MODEL_ARTIFACT_DIR"]), quick=True)


@pytest.fixture
def readiness_model(trained_artifact):
    """Registers + activates the session model in the (freshly truncated) test DB."""
    from app.ml.registry import registry
    from ml_pipeline.train import register

    register(trained_artifact, activate=True)
    registry.warm()
    assert registry.active_available(), registry.status()
    yield registry.active()
    registry._active = None


@pytest.fixture
def app():
    from app.main import create_app

    return create_app()


class ApiClient(TestClient):
    """TestClient that behaves like the SPA: sends the anti-CSRF header and echoes the CSRF
    cookie into X-CSRF-Token once signed in."""

    def request(self, method, url, **kwargs):  # type: ignore[override]
        headers = dict(kwargs.pop("headers", None) or {})
        headers.setdefault("X-Requested-With", "twinpath")
        csrf = self.cookies.get("tp_csrf")
        if csrf:
            headers.setdefault("X-CSRF-Token", csrf)
        return super().request(method, url, headers=headers, **kwargs)


@pytest.fixture
def client(app) -> Iterator[ApiClient]:
    with ApiClient(app, base_url="http://testserver") as c:
        yield c


@pytest.fixture
def make_client(app):
    clients: list[ApiClient] = []

    def _make() -> ApiClient:
        c = ApiClient(app, base_url="http://testserver")
        c.__enter__()
        clients.append(c)
        return c

    yield _make
    for c in clients:
        c.__exit__(None, None, None)


STRONG_PASSWORD = "correct-horse-battery-staple-42"  # gitleaks:allow — test-only fixture password


def outbox_tokens(kind: str) -> list[str]:
    from email import message_from_bytes, policy

    outbox = Path(os.environ["DATA_DIR"]) / "outbox"
    pattern = re.compile(rf"/{kind}#token=([A-Za-z0-9_\-]+)")
    tokens: list[str] = []
    for f in sorted(outbox.glob("*.eml")) if outbox.exists() else []:
        msg = message_from_bytes(f.read_bytes(), policy=policy.default)
        tokens += pattern.findall(msg.get_content())  # type: ignore[attr-defined]
    return tokens


def register(client: TestClient, email: str, password: str = STRONG_PASSWORD, name: str = "Test Student") -> None:
    r = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "display_name": name, "accept_profile_processing": True},
    )
    assert r.status_code == 202, r.text


def login(client: TestClient, email: str, password: str = STRONG_PASSWORD) -> dict:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def set_role(owner_engine, email: str, role: str) -> None:
    with owner_engine.begin() as conn:
        conn.execute(text("UPDATE users SET role=:r WHERE email=:e"), {"r": role, "e": email})


@pytest.fixture
def student(make_client):
    """A registered + signed-in student client."""

    def _student(email: str = "asha@example.edu") -> ApiClient:
        c = make_client()
        register(c, email)
        login(c, email)
        return c

    return _student
