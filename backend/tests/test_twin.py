from __future__ import annotations

from datetime import date

from sqlalchemy import text

API = "/api/v1"


def _skill_id(client, slug: str) -> int:
    skills = client.get(f"{API}/catalogue/skills").json()["skills"]
    return next(s["id"] for s in skills if s["slug"] == slug)


def _role_id(client, slug: str) -> int:
    return next(r["id"] for r in client.get(f"{API}/roles").json()["roles"] if r["slug"] == slug)


def test_profile_update_creates_versioned_snapshots(seeded, student, owner_engine):
    c = student()
    body = {
        "degree": "B.Tech",
        "specialization": "Computer Engineering",
        "current_semester": 6,
        "graduation_year": 2027,
        "cgpa": 8.123,
        "career_interests": ["ML", "ml", " Data "],
        "learning_preferences": ["video", "project_based"],
        "weekly_hours": 10,
    }
    r = c.put(f"{API}/profile", json=body)
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["cgpa"] == 8.12 and p["career_interests"] == ["ML", "Data"] and p["twin_version"] == 1
    # identical update -> no new snapshot (content-addressed)
    assert c.put(f"{API}/profile", json=body).json()["twin_version"] == 1
    body["cgpa"] = 8.4
    assert c.put(f"{API}/profile", json=body).json()["twin_version"] == 2
    diff = c.get(f"{API}/twin/diff", params={"from_version": 1}).json()
    assert {"kind": "profile", "field": "cgpa", "before": 8.12, "after": 8.4} in diff["changes"]


def test_profile_validation_and_attendance_consent(seeded, student):
    c = student()
    assert c.put(f"{API}/profile", json={"cgpa": 11}).status_code == 422
    assert c.put(f"{API}/profile", json={"current_semester": 0}).status_code == 422
    assert c.put(f"{API}/profile", json={"unexpected": 1}).status_code == 422
    r = c.put(f"{API}/profile", json={"attendance_pct": 90})
    assert r.status_code == 403 and r.json()["error"]["code"] == "consent_required"


def test_unknown_vs_self_reported_vs_evidence_precedence(seeded, student):
    c = student()
    sql = _skill_id(c, "sql")
    skills = {s["skill_id"]: s for s in c.get(f"{API}/twin/skills").json()["items"]}
    assert skills[sql]["status"] == "unknown" and skills[sql]["estimated_level"] is None  # unknown, NOT zero

    assert c.put(f"{API}/twin/skills/{sql}", json={"self_rating": 4}).status_code == 200
    s = {x["skill_id"]: x for x in c.get(f"{API}/twin/skills").json()["items"]}[sql]
    assert s["status"] == "self_reported" and s["estimated_level"] == 4

    proj = {
        "title": "Sales dashboard",
        "skills": [{"skill_id": sql, "level": 2}],
        "is_deployed": True,
        "repo_url": "https://github.com/example/sales-dashboard",
    }
    assert c.post(f"{API}/twin/projects", json=proj).status_code == 201
    s = {x["skill_id"]: x for x in c.get(f"{API}/twin/skills").json()["items"]}[sql]
    # Unverified project evidence (trust .6) outranks the self-rating (trust .4).
    assert s["status"] == "unverified_evidence" and s["estimated_level"] == 2
    assert {sig["status"] for sig in s["signals"]} == {"unverified_evidence", "self_reported"}


def test_project_validation(seeded, student):
    c = student()
    bad_url = {"title": "X project", "repo_url": "javascript:alert(1)"}
    assert c.post(f"{API}/twin/projects", json=bad_url).status_code == 422
    http_url = {"title": "X project", "repo_url": "http://github.com/x"}
    assert c.post(f"{API}/twin/projects", json=http_url).status_code == 422
    future = {"title": "X project", "completed_on": str(date(2999, 1, 1))}
    assert c.post(f"{API}/twin/projects", json=future).status_code == 422
    # students can never set verification themselves
    forged = {"title": "X project", "verification_status": "verified"}
    assert c.post(f"{API}/twin/projects", json=forged).status_code == 422
    unknown_skill = {"title": "X project", "skills": [{"skill_id": 99999, "level": 2}]}
    assert c.post(f"{API}/twin/projects", json=unknown_skill).status_code == 422


def test_cross_user_isolation_idor(seeded, student):
    a, b = student("a@example.edu"), student("b@example.edu")
    pid = a.post(f"{API}/twin/projects", json={"title": "Private project A"}).json()["id"]
    assert b.put(f"{API}/twin/projects/{pid}", json={"title": "hijacked"}).status_code == 404
    assert b.delete(f"{API}/twin/projects/{pid}").status_code == 404
    assert all(p["id"] != pid for p in b.get(f"{API}/twin/projects").json())
    assert b.post(f"{API}/twin/verification-requests", json={"item_type": "project", "item_id": pid}).status_code == 404
    assert [p["title"] for p in a.get(f"{API}/twin/projects").json()] == ["Private project A"]


def test_rls_blocks_cross_user_rows_under_app_role(seeded, student, owner_engine):
    """Defence in depth: even raw SQL as the application role cannot read or write another
    student's rows once the transaction is scoped to a user."""
    from sqlalchemy import create_engine

    from tests.conftest import _test_db

    a, b = student("a@example.edu"), student("b@example.edu")
    a.post(f"{API}/twin/projects", json={"title": "A's project"})
    b.post(f"{API}/twin/projects", json={"title": "B's project"})
    with owner_engine.connect() as conn:
        ids = dict(conn.execute(text("SELECT email, id FROM users")).all())
    app_engine = create_engine(_test_db)
    try:
        with app_engine.begin() as conn:
            conn.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": str(ids["a@example.edu"])})
            titles = conn.execute(text("SELECT title FROM projects")).scalars().all()
            assert titles == ["A's project"]
            n = conn.execute(text("UPDATE projects SET title='x' WHERE user_id=:b"), {"b": ids["b@example.edu"]}).rowcount
            assert n == 0
        with app_engine.begin() as conn:
            conn.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": str(ids["a@example.edu"])})
            try:
                conn.execute(text("INSERT INTO projects (user_id, title) VALUES (:b, 'forged')"), {"b": ids["b@example.edu"]})
                raise AssertionError("RLS should have rejected the insert")
            except Exception as exc:
                assert "row-level security" in str(exc)
        with app_engine.begin() as conn:  # no subject at all -> nothing visible
            assert conn.execute(text("SELECT count(*) FROM projects")).scalar_one() == 0
            # the app role cannot tamper with the audit trail
            try:
                conn.execute(text("DELETE FROM audit_events"))
                raise AssertionError("app role must not delete audit events")
            except Exception as exc:
                assert "permission denied" in str(exc)
    finally:
        app_engine.dispose()


def test_verified_item_edit_resets_verification(seeded, student, owner_engine):
    c = student()
    pid = c.post(f"{API}/twin/projects", json={"title": "Chat app"}).json()["id"]
    with owner_engine.begin() as conn:
        conn.execute(text("UPDATE projects SET verification_status='verified' WHERE id=:i"), {"i": pid})
    r = c.put(f"{API}/twin/projects/{pid}", json={"title": "Chat app v2 (rewritten)"})
    assert r.json()["verification_status"] == "unverified"


def test_role_preferences_and_onboarding(seeded, student):
    c = student()
    assert c.post(f"{API}/profile/onboarding/complete").status_code == 422
    da, ds = _role_id(c, "data-analyst"), _role_id(c, "data-scientist")
    assert c.put(f"{API}/profile/roles", json={"target_role_id": 99999}).status_code == 422
    r = c.put(f"{API}/profile/roles", json={"target_role_id": da, "preferred_role_ids": [ds]})
    assert r.status_code == 200 and r.json()["preferred_role_ids"] == [da, ds]
    assert c.post(f"{API}/profile/onboarding/complete").status_code == 200
    assert c.get(f"{API}/auth/me").json()["onboarding_completed"] is True


def test_self_reported_assessment_is_unverified(seeded, student):
    c = student()
    cat = c.get(f"{API}/twin/assessments").json()["catalogue"]
    sql_practical = next(a for a in cat if a["slug"] == "sql-practical")
    over = {"assessment_id": sql_practical["id"], "score": 150, "taken_on": "2026-09-01"}
    assert c.post(f"{API}/twin/assessments", json=over).status_code == 422
    ok = c.post(f"{API}/twin/assessments", json={**over, "score": 90}).json()
    assert ok["verification_status"] == "unverified" and ok["source"] == "self_reported"
    sql = _skill_id(c, "sql")
    s = {x["skill_id"]: x for x in c.get(f"{API}/twin/skills").json()["items"]}[sql]
    assert s["status"] == "unknown"  # unverified assessments do not count as 'assessed'


def test_completeness(seeded, student):
    c = student()
    before = c.get(f"{API}/twin/completeness").json()
    c.put(
        f"{API}/profile",
        json={
            "degree": "B.E.",
            "specialization": "IT",
            "current_semester": 5,
            "graduation_year": 2028,
            "cgpa": 7.5,
            "weekly_hours": 6,
            "learning_preferences": ["video"],
        },
    )
    after = c.get(f"{API}/twin/completeness").json()
    assert after["overall"] > before["overall"]
    assert next(s for s in after["sections"] if s["key"] == "academic")["complete"] is True


def test_profile_patch_is_partial(seeded, student):
    c = student()
    c.put(f"{API}/profile", json={"degree": "B.Tech", "cgpa": 8.0, "weekly_hours": 9})
    r = c.patch(f"{API}/profile", json={"weekly_hours": 12})
    assert r.status_code == 200
    body = r.json()
    assert body["weekly_hours"] == 12 and body["degree"] == "B.Tech" and body["cgpa"] == 8.0


def test_login_response_reflects_completed_onboarding(seeded, make_client):
    """Regression: the login response is built before the request is RLS-scoped; it must still see
    the student's own profile (found by the Playwright journey test)."""
    from tests.conftest import login, register

    c = make_client()
    register(c, "onboarded@example.edu")
    login(c, "onboarded@example.edu")
    rid = c.get(f"{API}/roles").json()["roles"][0]["id"]
    c.put(f"{API}/profile/roles", json={"target_role_id": rid})
    assert c.post(f"{API}/profile/onboarding/complete").status_code == 200
    c.post(f"{API}/auth/logout")
    body = login(c, "onboarded@example.edu")
    assert body["me"]["onboarding_completed"] is True
