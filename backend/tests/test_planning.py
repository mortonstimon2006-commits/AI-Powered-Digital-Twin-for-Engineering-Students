from __future__ import annotations

from tests.test_career import _setup_student

API = "/api/v1"


def test_knowledge_graph_built_from_data(seeded, student):
    c = student()
    da, skills = _setup_student(c)
    r = c.get(f"{API}/knowledge-graph", params={"role_id": da["id"]})
    assert r.status_code == 200, r.text
    g = r.json()
    node_ids = {n["id"] for n in g["nodes"]}
    assert "student:me" in node_ids and f"role:{da['id']}" in node_ids
    assert f"skill:{skills['sql']}" in node_ids
    sql_node = next(n for n in g["nodes"] if n["id"] == f"skill:{skills['sql']}")
    assert sql_node["level"] == 2 and sql_node["status"] == "self_reported" and len(sql_node["position"]) == 3
    edge_types = {e["type"] for e in g["edges"]}
    assert {"STUDENT_HAS_SKILL", "SKILL_PREREQUISITE_OF"} <= edge_types
    assert edge_types & {"SKILL_REQUIRED_FOR_ROLE", "ROLE_REQUIRES_TECHNOLOGY"}
    has = [e for e in g["edges"] if e["type"] == "STUDENT_HAS_SKILL"]
    assert all(e["provenance"] == "self_reported" for e in has)  # only self-ratings recorded so far
    # deterministic layout
    assert c.get(f"{API}/knowledge-graph", params={"role_id": da["id"]}).json()["nodes"] == g["nodes"]


def test_graph_insights_queries(seeded, student):
    c = student()
    da, _ = _setup_student(c)
    ins = c.get(f"{API}/knowledge-graph/insights").json()
    assert ins["role_id"] == da["id"]
    assert ins["resources_for_top_gaps"] and all(
        r["url"].startswith("https://") for g in ins["resources_for_top_gaps"] for r in g["resources"]
    )
    assert len(ins["alternative_roles"]) == 6
    assert any(r["is_target"] for r in ins["alternative_roles"])
    for unlock in ins["multi_role_unlocks"]:
        assert unlock["role_count"] >= 2
    # e.g. BI tools needs data-visualization which is unknown -> a blocking prerequisite is reported
    assert any(b["blocked_skill"] == "BI & Dashboards" for b in ins["blocking_prerequisites"])


def test_inferred_edges_are_labelled(seeded, student, owner_engine):
    from sqlalchemy import text

    c = student()
    _setup_student(c)
    skills = {s["slug"]: s["id"] for s in c.get(f"{API}/catalogue/skills").json()["skills"]}
    pid = c.post(
        f"{API}/twin/projects",
        json={"title": "Normalised booking schema", "skills": [{"skill_id": skills["database-design"], "level": 3}]},
    ).json()["id"]
    with owner_engine.begin() as conn:
        conn.execute(text("UPDATE projects SET verification_status='verified' WHERE id=:i"), {"i": pid})
        conn.execute(text("DELETE FROM student_skills WHERE skill_id=:s"), {"s": skills["sql"]})
    g = c.get(f"{API}/knowledge-graph").json()
    inferred = [e for e in g["edges"] if e["provenance"] == "inferred"]
    assert any(e["target"] == f"skill:{skills['sql']}" and e["type"] == "STUDENT_LIKELY_HAS_SKILL" for e in inferred)


def test_roadmap_generation_progress_and_regeneration(seeded, student):
    c = student()
    da, skills = _setup_student(c)
    assert c.get(f"{API}/roadmaps/active").json() == {"exists": False}
    r = c.post(f"{API}/roadmaps/generate", json={"hours_per_week": 6})
    assert r.status_code == 200, r.text
    rm = r.json()
    items = rm["items"]
    assert items and rm["role_id"] == da["id"] and rm["hours_per_week"] == 6
    # prerequisites never come after the skills they unlock
    pos = {i["skill_name"]: i["position"] for i in items}
    for it in items:
        for pre in it["prerequisites"]:
            assert pos[pre] < it["position"], (pre, it["skill_name"])
    for it in items:
        assert it["effort_hours"][0] <= it["effort_hours"][1] and it["week_start"] <= it["week_end"]
        assert it["reason"] and it["completion_criteria"]
        if it["resource"]:
            assert it["resource"]["url"].startswith("https://")
    # progress
    first = items[0]["id"]
    upd = c.patch(f"{API}/roadmaps/items/{first}", json={"status": "completed"}).json()
    assert upd["status"] == "completed" and "does not change your skill estimate" in upd["evidence_hint"]
    assert c.get(f"{API}/roadmaps/active").json()["progress"]["completed"] == 1
    # profile change -> stale -> regenerate carries progress and reports a diff
    c.put(f"{API}/twin/skills/{skills['statistics']}", json={"self_rating": 3})
    assert c.get(f"{API}/roadmaps/active").json()["stale"] is True
    regen = c.post(f"{API}/roadmaps/generate", json={"hours_per_week": 6}).json()
    assert "comparison_with_previous" in regen
    assert regen["previous_roadmap_id"] == rm["id"]
    same = [i for i in regen["items"] if i["skill_name"] == items[0]["skill_name"] and i["action"] == items[0]["action"]]
    if same:
        assert same[0]["status"] == "completed"
    archived = c.get(f"{API}/roadmaps/{rm['id']}").json()
    assert archived["status"] == "archived"
    assert c.patch(f"{API}/roadmaps/items/{first}", json={"status": "in_progress"}).status_code == 409


def test_roadmap_reorder_warns_on_prerequisite_violation(seeded, student):
    c = student()
    _setup_student(c)
    rm = c.post(f"{API}/roadmaps/generate", json={}).json()
    ids = [i["id"] for i in rm["items"]]
    assert c.put(f"{API}/roadmaps/{rm['id']}/order", json={"item_ids": ids[:-1]}).status_code == 422
    r = c.put(f"{API}/roadmaps/{rm['id']}/order", json={"item_ids": list(reversed(ids))})
    assert r.status_code == 200
    has_prereq_pairs = any(i["prerequisites"] for i in rm["items"])
    assert bool(r.json()["warnings"]) == has_prereq_pairs


def test_roadmap_isolation(seeded, student):
    a, b = student("a@example.edu"), student("b@example.edu")
    _setup_student(a)
    rm = a.post(f"{API}/roadmaps/generate", json={}).json()
    assert b.get(f"{API}/roadmaps/{rm['id']}").status_code == 404
    assert b.patch(f"{API}/roadmaps/items/{rm['items'][0]['id']}", json={"status": "completed"}).status_code == 404
    assert b.put(f"{API}/roadmaps/{rm['id']}/order", json={"item_ids": [i["id"] for i in rm["items"]]}).status_code == 404


def test_roadmap_requires_target_role(seeded, student):
    c = student()
    r = c.post(f"{API}/roadmaps/generate", json={})
    assert r.status_code == 422 and r.json()["error"]["code"] == "target_role_required"


def test_progress_timeline(seeded, student, readiness_model):
    c = student()
    _setup_student(c)
    c.post(f"{API}/readiness/analyse")
    c.post(f"{API}/roadmaps/generate", json={})
    t = c.get(f"{API}/progress/timeline").json()
    assert len(t["snapshots"]) >= 3 and len(t["predictions"]) == 1 and t["roadmap_events"]
    versions = [s["version"] for s in t["snapshots"]]
    assert versions == sorted(versions)
