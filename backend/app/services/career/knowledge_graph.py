"""Knowledge graph over the reference catalogue plus one student's overlay (NetworkX).

Node types : student, skill, role, resource, assessment, project
Edge types : SKILL_PREREQUISITE_OF, SKILL_REQUIRED_FOR_ROLE, ROLE_REQUIRES_TECHNOLOGY,
             RESOURCE_TEACHES_SKILL, ASSESSMENT_MEASURES_SKILL, STUDENT_HAS_SKILL,
             PROJECT_DEMONSTRATES_SKILL, STUDENT_BUILT_PROJECT, STUDENT_LIKELY_HAS_SKILL (inferred)
Provenance : framework | evidence | self_reported | inferred  — so the UI can distinguish
             recorded facts from inferences.

The global graph is cached per catalogue fingerprint (reference data only). The student
overlay is built per request and never cached, so no user's data can leak into another's.
NetworkX is sufficient at this scale (tens of roles, hundreds of skills/resources); see
docs/architecture.md for when Neo4j would be justified.
"""

from __future__ import annotations

import threading
from typing import Any

import networkx as nx

from app.services.career.gap_engine import RoleMatch, analyse_all_roles, analyse_role
from app.services.catalogue import Catalogue
from app.services.twin.proficiency import SkillEstimate
from app.services.twin.state import TwinState

_cache: dict[str, nx.MultiDiGraph] = {}
_lock = threading.Lock()


def skill_node(sid: int) -> str:
    return f"skill:{sid}"


def global_graph(catalogue: Catalogue) -> nx.MultiDiGraph:
    with _lock:
        if catalogue.fingerprint in _cache:
            return _cache[catalogue.fingerprint]
    g = nx.MultiDiGraph()
    for s in catalogue.skills.values():
        g.add_node(skill_node(s.id), type="skill", label=s.name, category=s.category, kind=s.kind, ref_id=s.id)
    for r in catalogue.roles.values():
        g.add_node(f"role:{r.id}", type="role", label=r.name, ref_id=r.id, version=r.version)
        for q in r.requirements:
            sk = catalogue.skills[q.skill_id]
            if sk.kind == "technology":
                g.add_edge(
                    f"role:{r.id}",
                    skill_node(q.skill_id),
                    type="ROLE_REQUIRES_TECHNOLOGY",
                    level=q.required_level,
                    importance=q.importance,
                    core=q.is_core,
                    provenance="framework",
                )
            else:
                g.add_edge(
                    skill_node(q.skill_id),
                    f"role:{r.id}",
                    type="SKILL_REQUIRED_FOR_ROLE",
                    level=q.required_level,
                    importance=q.importance,
                    core=q.is_core,
                    provenance="framework",
                )
    for sid, pre in catalogue.prerequisites.items():
        for pid, lvl in pre:
            g.add_edge(skill_node(pid), skill_node(sid), type="SKILL_PREREQUISITE_OF", min_level=lvl, provenance="framework")
    for res in catalogue.resources.values():
        g.add_node(
            f"resource:{res.id}",
            type="resource",
            label=res.title,
            ref_id=res.id,
            url=res.url,
            verification=res.verification_status,
            provider=res.provider,
        )
        for sid in res.skill_ids:
            if sid in catalogue.skills:
                g.add_edge(f"resource:{res.id}", skill_node(sid), type="RESOURCE_TEACHES_SKILL", provenance="framework")
    for aid, a in catalogue.assessments.items():
        g.add_node(f"assessment:{aid}", type="assessment", label=a["name"], ref_id=aid)
        for sid in catalogue.assessment_skills.get(aid, []):
            if sid in catalogue.skills:
                g.add_edge(f"assessment:{aid}", skill_node(sid), type="ASSESSMENT_MEASURES_SKILL", provenance="framework")
    with _lock:
        _cache.clear()
        _cache[catalogue.fingerprint] = g
    return g


def student_graph(catalogue: Catalogue, state: TwinState, estimates: dict[int, SkillEstimate]) -> nx.MultiDiGraph:
    g = global_graph(catalogue).copy()
    g.add_node("student:me", type="student", label="You")
    for sid, e in estimates.items():
        if not e.known:
            continue
        prov = "self_reported" if e.status == "self_reported" else "evidence"
        g.add_edge("student:me", skill_node(sid), type="STUDENT_HAS_SKILL", level=e.level, status=e.status, provenance=prov)
    for p in state.projects:
        g.add_node(f"project:{p.id}", type="project", label=p.title, verification=p.verification_status)
        g.add_edge("student:me", f"project:{p.id}", type="STUDENT_BUILT_PROJECT", provenance="evidence")
    for ev in state.evidence:
        if ev.source_type == "project":
            g.add_edge(
                f"project:{ev.source_id}",
                skill_node(ev.skill_id),
                type="PROJECT_DEMONSTRATES_SKILL",
                level=ev.level,
                verification=ev.verification_status,
                provenance="evidence",
            )
    # Inference (clearly labelled): demonstrating a skill at level >=3 with evidence suggests its
    # direct prerequisites are held at least at their minimum level, if they are otherwise unknown.
    for sid, e in estimates.items():
        if e.known and e.level is not None and e.level >= 3 and e.status != "self_reported":
            for pid, min_lvl in catalogue.prerequisites.get(sid, []):
                if not estimates[pid].known:
                    g.add_edge(
                        "student:me",
                        skill_node(pid),
                        type="STUDENT_LIKELY_HAS_SKILL",
                        level=min_lvl,
                        provenance="inferred",
                        because=catalogue.skills[sid].name,
                    )
    return g


# ----------------------------------------------------------------------------- queries


def blocking_prerequisites(catalogue: Catalogue, estimates: dict[int, SkillEstimate], role_id: int) -> list[dict[str, Any]]:
    """Which missing prerequisite skills block the student's progress towards a role?"""
    role = catalogue.roles[role_id]
    g = nx.DiGraph()
    for sid, pre in catalogue.prerequisites.items():
        for pid, lvl in pre:
            g.add_edge(pid, sid, min_level=lvl)
    out = []
    for q in role.requirements:
        e = estimates[q.skill_id]
        if e.known and e.level is not None and e.level >= q.required_level:
            continue
        if q.skill_id not in g:
            continue
        for anc in nx.ancestors(g, q.skill_id):
            path = nx.shortest_path(g, anc, q.skill_id)
            needed = g.edges[path[0], path[1]]["min_level"]
            ae = estimates[anc]
            if ae.level is None or ae.level < needed:
                out.append(
                    {
                        "blocked_skill": catalogue.skills[q.skill_id].name,
                        "blocked_skill_id": q.skill_id,
                        "prerequisite": catalogue.skills[anc].name,
                        "prerequisite_id": anc,
                        "needed_level": needed,
                        "current_level": ae.level,
                        "status": ae.status,
                        "path": [catalogue.skills[n].name for n in path],
                    }
                )
    out.sort(key=lambda x: (len(x["path"]), x["prerequisite"]))
    return out


def resources_for_top_gaps(catalogue: Catalogue, match: RoleMatch, k: int = 5) -> list[dict[str, Any]]:
    out = []
    for gap in [g for g in match.gaps if g.action in ("learn", "prerequisite", "assess")][:k]:
        current = gap.estimated_level or 0
        options = [catalogue.resources[r] for r in catalogue.resources_by_skill.get(gap.skill_id, [])]
        options.sort(key=lambda r: (r.verification_status != "verified", abs(r.level_min - (current + 1)), r.cost != "free"))
        out.append(
            {
                "skill": gap.skill_name,
                "skill_id": gap.skill_id,
                "priority": gap.priority,
                "action": gap.action,
                "resources": [
                    {
                        "id": r.id,
                        "title": r.title,
                        "url": r.url,
                        "provider": r.provider,
                        "verification_status": r.verification_status,
                        "cost": r.cost,
                    }
                    for r in options[:3]
                ],
            }
        )
    return out


def alternative_roles(
    catalogue: Catalogue, estimates: dict[int, SkillEstimate], target_role_id: int | None
) -> list[dict[str, Any]]:
    """Roles ranked by overlap with the student's DEMONSTRATED competencies (known levels)."""
    matches = analyse_all_roles(list(catalogue.roles.values()), estimates, catalogue)
    target_skills = (
        {q.skill_id for q in catalogue.roles[target_role_id].requirements} if target_role_id in catalogue.roles else set()
    )
    out = []
    for m in matches:
        role = catalogue.roles[m.role_id]
        met = [g.skill_name for g in m.gaps if g.action in ("maintain", "verify")]
        shared = {q.skill_id for q in role.requirements} & target_skills
        out.append(
            {
                "role_id": m.role_id,
                "role_name": m.role_name,
                "match": m.match,
                "match_upper": m.match_upper,
                "met_skills": met,
                "is_target": m.role_id == target_role_id,
                "shared_with_target": len(shared),
            }
        )
    return out


def multi_role_unlocks(
    catalogue: Catalogue, estimates: dict[int, SkillEstimate], role_ids: list[int] | None = None
) -> list[dict[str, Any]]:
    """Which single skill improvements close gaps in the most roles (weighted)?"""
    roles = [catalogue.roles[r] for r in (role_ids or list(catalogue.roles)) if r in catalogue.roles]
    agg: dict[int, dict[str, Any]] = {}
    for role in roles:
        m = analyse_role(role, estimates, catalogue)
        for g in m.gaps:
            if g.action in ("learn", "prerequisite", "assess"):
                a = agg.setdefault(g.skill_id, {"skill_id": g.skill_id, "skill": g.skill_name, "roles": [], "weight": 0.0})
                a["roles"].append({"role": role.name, "required_level": g.required_level})
                a["weight"] += g.weight
    ranked = sorted(agg.values(), key=lambda a: (-len(a["roles"]), -a["weight"], a["skill"]))
    for a in ranked:
        a["weight"] = round(a["weight"], 3)
        a["role_count"] = len(a["roles"])
    return [a for a in ranked if a["role_count"] >= 2]


# ----------------------------------------------------------------------------- visualisation payload


def visual_payload(
    g: nx.MultiDiGraph,
    *,
    role_id: int | None,
    include: set[str],
    estimates: dict[int, SkillEstimate],
    match: RoleMatch | None,
    max_nodes: int = 220,
) -> dict[str, Any]:
    keep: set[str] = {"student:me"} if "student:me" in g else set()
    if role_id is not None:
        role_node = f"role:{role_id}"
        keep.add(role_node)
        role_skills = {u for u, _, d in g.in_edges(role_node, data=True) if d["type"] == "SKILL_REQUIRED_FOR_ROLE"}
        role_skills |= {v for _, v, d in g.out_edges(role_node, data=True) if d["type"] == "ROLE_REQUIRES_TECHNOLOGY"}
        prereqs = set()
        for s in role_skills:
            prereqs |= set(nx.ancestors(g.subgraph([n for n in g if n.startswith("skill:")]), s))
        keep |= role_skills | prereqs
    else:
        keep |= {n for n, d in g.nodes(data=True) if d["type"] in ("skill", "role")}
    skill_nodes = {n for n in keep if n.startswith("skill:")}
    for n, d in g.nodes(data=True):
        t = d["type"]
        if t in include and t in ("resource", "assessment") and any(v in skill_nodes for v in g.successors(n)):
            keep.add(n)
        if t == "project" and "project" in include:
            keep.add(n)
    sub = g.subgraph(list(keep)[:max_nodes])

    layout_graph = nx.Graph()
    layout_graph.add_nodes_from(sub.nodes)
    layout_graph.add_edges_from((u, v) for u, v in sub.edges())
    fixed = {}
    pos_init = {}
    if "student:me" in layout_graph:
        pos_init["student:me"] = (0.0, 0.0, 0.0)
        fixed["student:me"] = True
    pos = nx.spring_layout(layout_graph, dim=3, seed=42, iterations=120, pos=pos_init or None, fixed=list(fixed) or None, k=None)

    gaps = {gp.skill_id: gp for gp in match.gaps} if match else {}
    nodes = []
    for n, d in sub.nodes(data=True):
        node: dict[str, Any] = {
            "id": n,
            "type": d["type"],
            "label": d.get("label", n),
            "position": [round(float(c), 4) for c in pos[n]],
        }
        if d["type"] == "skill":
            e = estimates.get(d["ref_id"])
            node.update(
                {
                    "category": d["category"],
                    "kind": d["kind"],
                    "level": e.level if e else None,
                    "status": e.status if e else "unknown",
                }
            )
            gp = gaps.get(d["ref_id"])
            if gp:
                node.update({"required_level": gp.required_level, "action": gp.action, "priority": gp.priority})
        elif d["type"] == "resource":
            node.update({"url": d["url"], "verification": d["verification"], "provider": d["provider"]})
        elif d["type"] == "project":
            node.update({"verification": d["verification"]})
        nodes.append(node)
    edges = []
    for u, v, d in sub.edges(data=True):
        edges.append(
            {
                "source": u,
                "target": v,
                "type": d["type"],
                "provenance": d.get("provenance", "framework"),
                **{k: d[k] for k in ("level", "min_level", "importance", "status", "because") if k in d},
            }
        )
    return {
        "nodes": nodes,
        "edges": edges,
        "counts": {"nodes": len(nodes), "edges": len(edges)},
        "legend": {
            "provenance": {
                "framework": "Defined by the role-skill framework",
                "evidence": "Backed by your recorded evidence or assessments",
                "self_reported": "Your self-rating only",
                "inferred": "Inferred by the app from a related skill — not recorded evidence",
            }
        },
    }
