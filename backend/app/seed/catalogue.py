"""Idempotent loader for the reference catalogue. Inserts what is missing; never overwrites
records an administrator may have edited (roles keep their admin-managed versions)."""

from __future__ import annotations

import networkx as nx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Assessment,
    AssessmentSkill,
    CareerRole,
    LearningResource,
    ResourceSkill,
    RoleSkillRequirement,
    Skill,
    SkillPrerequisite,
)
from app.seed import catalogue_data as data
from app.services.catalogue import snapshot_role_version


def _validate_static_data() -> None:
    slugs = {s[0] for s in data.SKILLS}
    g = nx.DiGraph()
    for skill, prereq, _ in data.PREREQUISITES:
        assert skill in slugs and prereq in slugs, f"unknown skill in prerequisite {skill}<-{prereq}"
        g.add_edge(prereq, skill)
    if not nx.is_directed_acyclic_graph(g):
        raise ValueError(f"prerequisite cycle: {nx.find_cycle(g)}")
    for role, (_, _, _, reqs) in data.ROLES.items():
        for r in reqs:
            assert r[0] in slugs, f"{role}: unknown skill {r[0]}"
    for res in data.RESOURCES:
        assert res[2].startswith("https://"), res[2]
        for s in res[10]:
            assert s in slugs, f"resource {res[0]}: unknown skill {s}"


def seed_catalogue(db: Session) -> dict[str, int]:
    _validate_static_data()
    counts = {"skills": 0, "prerequisites": 0, "roles": 0, "assessments": 0, "resources": 0}

    existing = {s.slug: s for s in db.scalars(select(Skill))}
    for slug, name, cat, kind, aliases, desc, exercise, criteria in data.SKILLS:
        if slug not in existing:
            sk = Skill(
                slug=slug,
                name=name,
                category=cat,
                kind=kind,
                aliases=[a.lower() for a in aliases],
                description=desc,
                practice_exercise=exercise,
                completion_criteria=criteria,
            )
            db.add(sk)
            existing[slug] = sk
            counts["skills"] += 1
    db.flush()
    ids = {slug: s.id for slug, s in existing.items()}

    have_prereq = {(p.skill_id, p.prerequisite_id) for p in db.scalars(select(SkillPrerequisite))}
    for skill, prereq, level in data.PREREQUISITES:
        key = (ids[skill], ids[prereq])
        if key not in have_prereq:
            db.add(SkillPrerequisite(skill_id=key[0], prerequisite_id=key[1], min_level=level))
            counts["prerequisites"] += 1

    roles = {r.slug for r in db.scalars(select(CareerRole))}
    for slug, (name, summary, description, reqs) in data.ROLES.items():
        if slug in roles:
            continue
        role = CareerRole(
            slug=slug, name=name, summary=summary, description=description, version=1, source_note=data.FRAMEWORK_SOURCE_NOTE
        )
        role.requirements = [
            RoleSkillRequirement(
                skill_id=ids[s],
                required_level=lvl,
                importance=imp,
                is_core=core,
                evidence_expected=ev,
                alt_group=grp,
                rationale=why,
            )
            for s, lvl, imp, core, ev, grp, why in reqs
        ]
        db.add(role)
        db.flush()
        snapshot_role_version(db, role, created_by=None)
        counts["roles"] += 1

    assessments = {a.slug for a in db.scalars(select(Assessment))}
    for slug, name, kind, max_score, desc, skills in data.ASSESSMENTS:
        if slug in assessments:
            continue
        a = Assessment(slug=slug, name=name, kind=kind, max_score=max_score, description=desc)
        db.add(a)
        db.flush()
        for s in skills:
            db.add(AssessmentSkill(assessment_id=a.id, skill_id=ids[s]))
        counts["assessments"] += 1

    urls = {r.url for r in db.scalars(select(LearningResource))}
    for title, provider, url, rtype, cost, lmin, lmax, hmin, hmax, desc, skills in data.RESOURCES:
        if url in urls:
            continue
        r = LearningResource(
            title=title,
            provider=provider,
            url=url,
            resource_type=rtype,
            cost=cost,
            level_min=lmin,
            level_max=lmax,
            est_hours_min=hmin,
            est_hours_max=hmax,
            description=desc,
            verification_status="unverified",
        )
        db.add(r)
        db.flush()
        for s in skills:
            db.add(ResourceSkill(resource_id=r.id, skill_id=ids[s]))
        counts["resources"] += 1

    db.flush()
    return counts
