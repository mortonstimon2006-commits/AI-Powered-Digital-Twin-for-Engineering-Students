from __future__ import annotations

from sqlalchemy import text

from tests.conftest import login, register, set_role
from tests.test_career import _setup_student

API = "/api/v1"


def _ids(owner_engine) -> dict[str, str]:
    with owner_engine.connect() as conn:
        return {e: str(i) for e, i in conn.execute(text("SELECT email, id FROM users")).all()}


def _staff(make_client, owner_engine, email: str, role: str):
    c = make_client()
    register(c, email)
    set_role(owner_engine, email, role)
    login(c, email)
    return c


def test_students_cannot_use_staff_or_admin_endpoints(seeded, student):
    c = student()
    assert c.get(f"{API}/staff/students").status_code == 403
    assert c.get(f"{API}/admin/users").status_code == 403
    assert c.get(f"{API}/admin/system").status_code == 403
    assert c.post(f"{API}/admin/roles", json={}).status_code in (403, 422)


def test_mentor_access_requires_link_and_consent(seeded, student, make_client, owner_engine):
    s = student("stu@example.edu")
    _setup_student(s)
    mentor = _staff(make_client, owner_engine, "mentor@example.edu", "mentor")
    admin = _staff(make_client, owner_engine, "admin@example.edu", "admin")
    ids = _ids(owner_engine)
    sid = ids["stu@example.edu"]

    assert mentor.get(f"{API}/staff/students/{sid}/overview").status_code == 404  # no link, no consent
    assert (
        admin.post(f"{API}/admin/mentor-links", json={"mentor_id": ids["mentor@example.edu"], "student_id": sid}).status_code
        == 201
    )
    assert mentor.get(f"{API}/staff/students/{sid}/overview").status_code == 404  # link but no consent
    assert mentor.get(f"{API}/staff/students").json()["items"] == []
    s.put(f"{API}/privacy/consents/mentor_sharing", json={"granted": True})
    ov = mentor.get(f"{API}/staff/students/{sid}/overview")
    assert ov.status_code == 200 and ov.json()["gaps"]["role"] == "Data Analyst"
    assert [x["id"] for x in mentor.get(f"{API}/staff/students").json()["items"]] == [sid]

    # mentor records a verified assessment -> the student's SQL becomes 'assessed'
    assessments = mentor.get(f"{API}/staff/assessments").json()["items"]
    sql_practical = next(a for a in assessments if a["slug"] == "sql-practical")
    r = mentor.post(
        f"{API}/staff/students/{sid}/assessments",
        json={"assessment_id": sql_practical["id"], "score": 80, "taken_on": "2026-09-30"},
    )
    assert r.status_code == 200
    sql = next(x for x in s.get(f"{API}/twin/skills").json()["items"] if x["slug"] == "sql")
    assert sql["status"] == "assessed" and sql["estimated_level"] == 3.2

    # verification workflow
    pid = s.post(f"{API}/twin/projects", json={"title": "Dashboard"}).json()["id"]
    s.post(f"{API}/twin/verification-requests", json={"item_type": "project", "item_id": pid})
    queue = mentor.get(f"{API}/staff/verification-queue").json()["items"]
    assert any(q["item_id"] == pid for q in queue)
    assert (
        mentor.post(
            f"{API}/staff/students/{sid}/verify", json={"item_type": "project", "item_id": pid, "decision": "verified"}
        ).status_code
        == 200
    )
    assert s.get(f"{API}/twin/projects").json()[0]["verification_status"] == "verified"

    # assessor label is frozen against a snapshot
    assert (
        mentor.post(
            f"{API}/staff/students/{sid}/readiness-labels", json={"label": "not_ready", "rubric": {"sql": 3, "communication": 2}}
        ).status_code
        == 200
    )
    with owner_engine.connect() as conn:
        row = conn.execute(text("SELECT snapshot_id, is_research_consented FROM readiness_labels")).one()
    assert row.snapshot_id is not None and row.is_research_consented is False

    # withdrawing consent revokes access immediately
    s.put(f"{API}/privacy/consents/mentor_sharing", json={"granted": False})
    assert mentor.get(f"{API}/staff/students/{sid}/overview").status_code == 404
    with owner_engine.connect() as conn:
        denied = conn.execute(
            text("SELECT count(*) FROM audit_events WHERE action='staff.access' AND outcome='denied'")
        ).scalar_one()
    assert denied >= 3


def test_admin_user_management_revokes_sessions(seeded, student, make_client, owner_engine):
    s = student("stu@example.edu")
    admin = _staff(make_client, owner_engine, "admin@example.edu", "admin")
    ids = _ids(owner_engine)
    assert admin.patch(f"{API}/admin/users/{ids['admin@example.edu']}", json={"role": "student"}).status_code == 422
    r = admin.patch(f"{API}/admin/users/{ids['stu@example.edu']}", json={"role": "mentor"})
    assert r.status_code == 200 and r.json()["role"] == "mentor"
    assert s.get(f"{API}/auth/me").status_code == 401  # privilege change forced re-authentication
    users = admin.get(f"{API}/admin/users", params={"search": "stu@"}).json()
    assert users["total"] == 1 and users["items"][0]["role"] == "mentor"
    assert admin.get(f"{API}/admin/audit", params={"action": "admin."}).json()["items"]


def test_role_versioning_and_staleness(seeded, student, make_client, owner_engine):
    s = student()
    da, _ = _setup_student(s)
    s.post(f"{API}/roadmaps/generate", json={})
    admin = _staff(make_client, owner_engine, "admin@example.edu", "admin")
    role = s.get(f"{API}/roles/{da['id']}").json()
    reqs = [
        {k: q[k] for k in ("skill_id", "required_level", "importance", "is_core", "evidence_expected", "alt_group", "rationale")}
        for q in role["requirements"]
    ]
    reqs[0]["required_level"] = 4
    body = {
        "slug": role["slug"],
        "name": role["name"],
        "summary": role["summary"],
        "description": role["description"],
        "source_note": role["source_note"] + " Revised by admin.",
        "requirements": reqs,
    }
    r = admin.put(f"{API}/admin/roles/{da['id']}", json=body)
    assert r.status_code == 200 and r.json()["version"] == 2
    assert s.get(f"{API}/roles/{da['id']}").json()["version"] == 2
    rm = s.get(f"{API}/roadmaps/active").json()
    assert rm["stale"] and any("role requirements" in reason for reason in rm["stale_reasons"])
    with owner_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM role_versions WHERE role_id=:r"), {"r": da["id"]}).scalar_one() == 2


def test_prerequisite_cycle_rejected(seeded, make_client, owner_engine):
    admin = _staff(make_client, owner_engine, "admin@example.edu", "admin")
    skills = {s["slug"]: s["id"] for s in admin.get(f"{API}/catalogue/skills").json()["skills"]}
    # data-structures <- algorithms already exists; making algorithms a prerequisite of data-structures is a cycle
    r = admin.put(
        f"{API}/admin/skills/{skills['data-structures']}/prerequisites", json={"prerequisites": [[skills["algorithms"], 2]]}
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "prerequisite_cycle"


def test_resource_ssrf_guard(seeded, make_client, owner_engine):
    admin = _staff(make_client, owner_engine, "admin@example.edu", "admin")
    sid = admin.get(f"{API}/catalogue/skills").json()["skills"][0]["id"]
    base = {
        "title": "Internal page",
        "provider": "x",
        "resource_type": "documentation",
        "level_min": 1,
        "level_max": 2,
        "est_hours_min": 1,
        "est_hours_max": 2,
        "skill_ids": [sid],
    }
    for url in (
        "https://127.0.0.1/admin",
        "https://localhost/x",
        "https://169.254.169.254/latest/meta-data",
        "http://example.com/plain-http",
    ):
        assert admin.post(f"{API}/admin/resources", json={**base, "url": url}).status_code == 422, url


def test_model_activation_refuses_tampered_artifact(seeded, make_client, owner_engine, readiness_model):
    admin = _staff(make_client, owner_engine, "admin@example.edu", "admin")
    models = admin.get(f"{API}/admin/models").json()
    mid = models["items"][0]["id"]
    with owner_engine.begin() as conn:
        conn.execute(text("UPDATE model_versions SET artifact_sha256 = repeat('0', 64), status='candidate'"))
    r = admin.post(f"{API}/admin/models/{mid}/activate")
    assert r.status_code == 422 and r.json()["error"]["code"] == "model_invalid"


def test_admin_system_status(seeded, make_client, owner_engine):
    admin = _staff(make_client, owner_engine, "admin@example.edu", "admin")
    st = admin.get(f"{API}/admin/system").json()
    assert st["database"] == "ok" and "ollama" in st and "mentor_queue" in st and st["counts"]["users"] == 1


def test_feedback_is_listed_for_admins_anonymously_and_rate_limited(seeded, student, make_client, owner_engine):
    s = student()
    sent = s.post(
        f"{API}/feedback",
        json={"target_type": "gap_analysis", "target_id": "/app/gaps", "rating": 4, "comment": "  Clear gap list  "},
    )
    assert sent.status_code == 200
    assert s.post(f"{API}/feedback", json={"target_type": "general", "rating": 2, "comment": "Login was slow"}).status_code == 200
    assert s.get(f"{API}/admin/feedback").status_code == 403  # students cannot read the list

    admin = _staff(make_client, owner_engine, "admin@example.edu", "admin")
    listed = admin.get(f"{API}/admin/feedback").json()
    assert listed["total"] == 2
    assert [i["comment"] for i in listed["items"]] == ["Login was slow", "Clear gap list"]  # newest first, trimmed
    assert listed["items"][1]["target_id"] == "/app/gaps"
    assert not {"user_id", "email", "display_name"} & set(listed["items"][0])  # anonymous by design
    only_gaps = admin.get(f"{API}/admin/feedback", params={"target_type": "gap_analysis"}).json()
    assert only_gaps["total"] == 1 and only_gaps["items"][0]["rating"] == 4

    statuses = {s.post(f"{API}/feedback", json={"target_type": "general", "rating": 5}).status_code for _ in range(30)}
    assert 429 in statuses  # 30 per hour per user, including the two above
