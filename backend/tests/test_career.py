from __future__ import annotations

import math

from sqlalchemy import text

from app.services.career.gap_engine import GapConfig, analyse_role
from app.services.catalogue import Catalogue, Requirement, RoleInfo, SkillInfo
from app.services.twin.proficiency import SkillEstimate, pct_to_level

API = "/api/v1"


# ----------------------------------------------------------------------------- pure engine


def _catalogue() -> Catalogue:
    skills = {i: SkillInfo(i, f"s{i}", f"Skill {i}", "programming", "concept", "", (), "", "") for i in range(1, 6)}
    prereqs = {2: [(1, 2)]}  # skill 2 needs skill 1 at level 2
    return Catalogue("fp", skills, {}, prereqs, {}, {}, {}, {})


def _role(reqs: list[Requirement]) -> RoleInfo:
    return RoleInfo(1, "r", "Role", "", "", 1, "test", tuple(reqs))


def _est(levels: dict[int, tuple[float | None, str]]) -> dict[int, SkillEstimate]:
    out = {}
    for sid in range(1, 6):
        lvl, status = levels.get(sid, (None, "unknown"))
        trust = {"assessed": 1.0, "verified_evidence": 0.85, "unverified_evidence": 0.6, "self_reported": 0.4}.get(status, 0)
        signals = [{"status": status, "level": lvl, "source": "project"}] if lvl is not None else []
        out[sid] = SkillEstimate(sid, lvl, status, trust, signals=signals)
    return out


def test_match_bounds_and_unknown_is_not_zero():
    role = _role([Requirement(1, 2, 1.0, True, "any", None, ""), Requirement(3, 4, 1.0, True, "any", None, "")])
    m = analyse_role(role, _est({1: (2, "assessed")}), _catalogue())
    assert m.match == 0.5  # skill 1 fully met, skill 3 unknown counts as not demonstrated
    assert m.match_upper == 1.0  # ...but could be fully met once assessed
    assert m.known_share == 0.5 and m.unknown_count == 1
    unknown = next(g for g in m.gaps if g.skill_id == 3)
    assert unknown.action == "assess" and unknown.gap is None and unknown.estimated_level is None


def test_alternative_group_uses_best_member():
    role = _role([Requirement(1, 3, 1.0, True, "any", "lang", ""), Requirement(4, 3, 1.0, True, "any", "lang", "")])
    m = analyse_role(role, _est({1: (1, "assessed"), 4: (3, "assessed")}), _catalogue())
    assert m.match == 1.0 and len(m.gaps) == 1 and m.gaps[0].skill_id == 4
    assert m.gaps[0].alternatives == ["Skill 1"]


def test_prerequisite_action_and_priority_ordering():
    role = _role([Requirement(1, 3, 0.5, True, "any", None, ""), Requirement(2, 3, 1.0, True, "any", None, "")])
    m = analyse_role(role, _est({1: (1, "assessed"), 2: (1, "assessed")}), _catalogue())
    g2 = next(g for g in m.gaps if g.skill_id == 2)
    g1 = next(g for g in m.gaps if g.skill_id == 1)
    assert g2.action == "prerequisite" and not g2.prerequisites[0]["met"]
    assert g1.blocking_count == 1  # skill 1 blocks skill 2
    # gap formula: W × (gap/L) × (1 + blocking_bonus × B)
    assert math.isclose(g1.priority, 0.5 * (2 / 3) * (1 + 0.2 * 1), rel_tol=1e-3)


def test_optional_weight_is_configurable():
    role = _role([Requirement(1, 2, 1.0, True, "any", None, ""), Requirement(3, 2, 1.0, False, "any", None, "")])
    est = _est({1: (2, "assessed"), 3: (0, "assessed")})
    assert analyse_role(role, est, _catalogue(), config=GapConfig(optional_weight=0.5)).match == round(1 / 1.5, 4)
    assert analyse_role(role, est, _catalogue(), config=GapConfig(optional_weight=0.0)).match == 1.0


def test_verify_action_for_self_reported_only():
    role = _role([Requirement(1, 2, 1.0, True, "assessment", None, "")])
    m = analyse_role(role, _est({1: (3, "self_reported")}), _catalogue())
    assert m.gaps[0].action == "verify" and m.gaps[0].evidence_met is False


def test_pct_to_level_mapping():
    assert pct_to_level(0) == 0 and pct_to_level(50) == 2 and pct_to_level(100) == 4 and pct_to_level(130) == 4


# ----------------------------------------------------------------------------- API


def _setup_student(client):
    roles = client.get(f"{API}/roles").json()["roles"]
    da = next(r for r in roles if r["slug"] == "data-analyst")
    skills = {s["slug"]: s["id"] for s in client.get(f"{API}/catalogue/skills").json()["skills"]}
    client.put(
        f"{API}/profile",
        json={
            "degree": "B.Tech",
            "specialization": "IT",
            "current_semester": 6,
            "graduation_year": 2027,
            "cgpa": 7.6,
            "weekly_hours": 8,
        },
    )
    client.put(f"{API}/profile/roles", json={"target_role_id": da["id"]})
    client.put(
        f"{API}/twin/skills",
        json={
            "ratings": [
                {"skill_id": skills["sql"], "self_rating": 2},
                {"skill_id": skills["python"], "self_rating": 3},
                {"skill_id": skills["statistics"], "self_rating": 2},
                {"skill_id": skills["spreadsheets"], "self_rating": 3},
            ]
        },
    )
    return da, skills


def test_role_catalogue_is_public_and_versioned(seeded, client):
    body = client.get(f"{API}/roles").json()
    assert len(body["roles"]) == 6
    assert "not derived from a job-postings dataset" in body["framework_note"].lower()
    for role in body["roles"]:
        assert role["version"] >= 1 and role["requirements"] and role["source_note"]


def test_gap_analysis_api(seeded, student):
    c = student()
    da, _ = _setup_student(c)
    r = c.get(f"{API}/skill-gaps/roles/{da['id']}")
    assert r.status_code == 200
    body = r.json()
    assert 0 <= body["match"] <= body["match_upper"] <= 1
    sql = next(g for g in body["gaps"] if g["skill_slug"] == "sql")
    assert sql["required_level"] == 3 and sql["estimated_level"] == 2 and sql["action"] == "learn"
    assert sql["resources"] and all(res["url"].startswith("https://") for res in sql["resources"])
    assert any(g["action"] == "assess" for g in body["gaps"])  # unknown skills ask for a baseline
    priorities = [g["priority"] for g in body["gaps"]]
    assert priorities == sorted(priorities, reverse=True)
    # configurable assumptions are validated
    assert c.get(f"{API}/skill-gaps/roles/{da['id']}", params={"optional_weight": 2}).status_code == 422
    summary = c.get(f"{API}/skill-gaps/summary").json()
    assert len(summary["matches"]) == 6 and "not hiring probabilities" in summary["disclaimer"]


def test_sensitivity_is_reproducible(seeded, student):
    c = student()
    _setup_student(c)
    a = c.get(f"{API}/skill-gaps/sensitivity", params={"samples": 60}).json()
    b = c.get(f"{API}/skill-gaps/sensitivity", params={"samples": 60}).json()
    assert a == b and 0 <= a["top_role_stability"] <= 1


def test_readiness_unavailable_without_model(seeded, student):
    c = student()
    r = c.post(f"{API}/readiness/analyse").json()
    assert r["available"] is False and "No estimate" in r["message"]
    assert c.get(f"{API}/readiness/latest").json()["exists"] is False


def test_readiness_with_model(seeded, student, readiness_model):
    c = student()
    _setup_student(c)
    r = c.post(f"{API}/readiness/analyse")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["available"] and body["model_version"] == readiness_model.version
    assert body["band"] in {"not_yet_ready", "developing", "interview_ready"}
    assert any(w["code"] == "synthetic_model" for w in body["warnings"])
    assert "raw_score" not in body and "model_db_id" not in body
    if body["probability"]:
        assert (body["probability"]["value"] * 20) % 1 == 0  # rounded to 5%, no false precision
    exp = body["explanation"]
    calibrated = body["calibrated_score"]
    assert exp["output_space"] in {"log_odds", "probability"}
    assert "attributions" in body["summary"] and "not proof" in body["summary"]
    latest = c.get(f"{API}/readiness/latest").json()
    assert latest["exists"] and latest["stale"] is False
    c.put(f"{API}/profile", json={"cgpa": 9.1, "current_semester": 6})
    assert c.get(f"{API}/readiness/latest").json()["stale"] is True
    assert calibrated is not None


def test_shap_explanation_matches_model(seeded, student, readiness_model):
    import numpy as np
    import pandas as pd

    from app.ml.feature_schema import FEATURE_NAMES
    from app.services.career.readiness import predict

    feats = dict.fromkeys(FEATURE_NAMES)
    feats.update(cgpa=8.0, semester=7.0, lvl_dsa=2.5, projects=3.0, deployed_projects=1.0, coding_assessment_pct=70.0)
    result = predict(feats)
    X = pd.DataFrame([[np.nan if feats[f] is None else feats[f] for f in FEATURE_NAMES]], columns=list(FEATURE_NAMES))
    raw = float(readiness_model.pipeline.predict_proba(X)[0, 1])
    target = math.log(raw / (1 - raw)) if result["explanation"]["output_space"] == "log_odds" else raw
    assert math.isclose(result["explanation"]["sum_check"], target, abs_tol=1e-3)


def test_simulation_never_touches_real_twin(seeded, student, readiness_model, owner_engine):
    c = student()
    da, skills = _setup_student(c)
    with owner_engine.connect() as conn:
        snaps_before = conn.execute(text("SELECT count(*) FROM twin_snapshots")).scalar_one()
    skills_before = c.get(f"{API}/twin/skills").json()
    req = {
        "changes": {
            "skill_levels": [{"skill_id": skills["sql"], "level": 3}],
            "assessments": [{"kind": "mock_interview", "pct": 80}],
            "add_projects": 2,
            "add_deployed_projects": 1,
        },
        "role_ids": [da["id"]],
    }
    r = c.post(f"{API}/simulations/run", json=req)
    assert r.status_code == 200, r.text
    sim = r.json()
    assert sim["hypothetical"] is True
    role = sim["roles"][0]
    assert role["hypothetical"]["match"] >= role["baseline"]["match"]
    assert any(ch["skill"] == "SQL" for ch in role["changed_skills"])
    assert sim["readiness"]["baseline"]["model_version"] == sim["readiness"]["hypothetical"]["model_version"]
    assert any("HYPOTHETICAL" in lim for lim in sim["limitations"])
    # the real twin is unchanged
    with owner_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM twin_snapshots")).scalar_one() == snaps_before
        assert conn.execute(text("SELECT count(*) FROM projects")).scalar_one() == 0
    assert c.get(f"{API}/twin/skills").json() == skills_before


def test_simulation_validation(seeded, student):
    c = student()
    _setup_student(c)
    bad = [
        {"changes": {}},
        {"changes": {"add_projects": 1, "add_deployed_projects": 2}},
        {"changes": {"skill_levels": [{"skill_id": 99999, "level": 3}]}},
        {"changes": {"skill_levels": [{"skill_id": 1, "level": 5}]}},
        {"changes": {"semester": 2}},
        {"changes": {"cgpa": 12}},
    ]
    for req in bad:
        assert c.post(f"{API}/simulations/run", json=req).status_code == 422, req


def test_saved_scenarios_are_private(seeded, student, readiness_model):
    a, b = student("a@example.edu"), student("b@example.edu")
    _setup_student(a)
    r = a.post(f"{API}/simulations/scenarios", json={"name": "SQL push", "request": {"changes": {"add_projects": 1}}})
    assert r.status_code == 201
    sid = r.json()["id"]
    assert b.get(f"{API}/simulations/scenarios").json()["items"] == []
    assert b.delete(f"{API}/simulations/scenarios/{sid}").status_code == 404
    assert a.delete(f"{API}/simulations/scenarios/{sid}").status_code == 200
