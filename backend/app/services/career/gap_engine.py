"""Role matching and skill-gap analysis (pure, documented, configurable).

Formula (see docs/methodology/skill-gap.md):

  For each requirement slot k (a single skill, or an alternative group collapsed to its
  best-covered member):
      W_k        = importance_k × (1 if core else optional_weight)
      E_k        = estimated level (None = unknown)
      coverage_k = min(E_k / L_k, 1)                     (unknown → excluded / bounded)
      gap_k      = max(L_k − E_k, 0)

  match            = Σ W_k·coverage_k(known; unknown→0) / Σ W_k      (demonstrated)
  match_upper      = Σ W_k·(coverage_k if known else 1) / Σ W_k      (if every unknown were met)
  known_share      = Σ W_k(known) / Σ W_k
  evidence_strength= Σ W_k·trust_k (known) / Σ W_k(known)

  priority_k = W_k × g_k × (1 + unlock_bonus·U_k) × (1 + blocking_bonus·B_k)
      g_k = gap_k / L_k  (unknown → unknown_gap_assumption)
      U_k = other preferred roles that also need this skill above the current level
      B_k = other gapped skills in this role that (transitively) depend on this skill

The match score is a profile-to-framework comparison. It is NOT a probability of being hired.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from typing import Any

import networkx as nx

from app.services.catalogue import Catalogue, Requirement, RoleInfo
from app.services.twin.proficiency import SkillEstimate


@dataclass(frozen=True)
class GapConfig:
    optional_weight: float = 0.5
    unlock_bonus: float = 0.15
    blocking_bonus: float = 0.2
    unknown_gap_assumption: float = 0.5
    verify_weight: float = 0.3

    def bounded(self) -> GapConfig:
        clamp = lambda v, lo, hi: max(lo, min(hi, v))  # noqa: E731
        return GapConfig(
            optional_weight=clamp(self.optional_weight, 0.0, 1.0),
            unlock_bonus=clamp(self.unlock_bonus, 0.0, 1.0),
            blocking_bonus=clamp(self.blocking_bonus, 0.0, 1.0),
            unknown_gap_assumption=clamp(self.unknown_gap_assumption, 0.0, 1.0),
            verify_weight=clamp(self.verify_weight, 0.0, 1.0),
        )


DEFAULT_CONFIG = GapConfig()


@dataclass
class SkillGap:
    skill_id: int
    skill_slug: str
    skill_name: str
    category: str
    required_level: int
    estimated_level: float | None
    status: str
    trust: float
    gap: float | None
    coverage: float | None
    importance: float
    weight: float
    is_core: bool
    evidence_expected: str
    evidence_met: bool
    alt_group: str | None
    alternatives: list[str]
    prerequisites: list[dict[str, Any]]
    blocking_count: int
    unlock_count: int
    priority: float
    action: str
    action_text: str
    rationale: str
    hypothetical: bool


@dataclass
class RoleMatch:
    role_id: int
    role_slug: str
    role_name: str
    role_version: int
    match: float
    match_upper: float
    known_share: float
    evidence_strength: float | None
    met_count: int
    gap_count: int
    unknown_count: int
    gaps: list[SkillGap] = field(default_factory=list)

    def to_dict(self, include_gaps: bool = True) -> dict[str, Any]:
        d = asdict(self)
        if not include_gaps:
            d.pop("gaps")
        return d


def _prereq_graph(catalogue: Catalogue) -> nx.DiGraph:
    g = nx.DiGraph()
    for sid, items in catalogue.prerequisites.items():
        for pid, lvl in items:
            g.add_edge(pid, sid, min_level=lvl)
    return g


def _descendants(graph: nx.DiGraph) -> dict[int, set[int]]:
    cached = graph.graph.get("_descendants")
    if cached is None:
        cached = {n: nx.descendants(graph, n) for n in graph.nodes}
        graph.graph["_descendants"] = cached
    return cached


def _slots(role: RoleInfo) -> list[list[Requirement]]:
    groups: dict[str, list[Requirement]] = {}
    slots: list[list[Requirement]] = []
    for req in role.requirements:
        if req.alt_group:
            if req.alt_group not in groups:
                groups[req.alt_group] = []
                slots.append(groups[req.alt_group])
            groups[req.alt_group].append(req)
        else:
            slots.append([req])
    return slots


def _coverage(est: SkillEstimate, req: Requirement) -> float | None:
    if est.level is None:
        return None
    return min(est.level / req.required_level, 1.0)


def _evidence_met(est: SkillEstimate, req: Requirement) -> bool:
    if req.evidence_expected == "any":
        return est.status in ("assessed", "verified_evidence", "unverified_evidence")
    if req.evidence_expected == "assessment":
        return est.status == "assessed"
    # 'project' expectation: any project/experience evidence signal at the required level
    return (
        any(s.get("source") in ("project", "experience") and s["level"] >= req.required_level for s in est.signals)
        or est.status == "assessed"
    )


def analyse_role(
    role: RoleInfo,
    estimates: dict[int, SkillEstimate],
    catalogue: Catalogue,
    *,
    config: GapConfig = DEFAULT_CONFIG,
    other_roles: list[RoleInfo] | None = None,
    graph: nx.DiGraph | None = None,
) -> RoleMatch:
    cfg = config.bounded()
    graph = graph if graph is not None else _prereq_graph(catalogue)
    other_roles = [r for r in (other_roles or []) if r.id != role.id]

    chosen: list[tuple[Requirement, SkillEstimate, list[str], float]] = []
    for slot in _slots(role):

        def score(req: Requirement) -> float:
            c = _coverage(estimates[req.skill_id], req)
            return -1.0 if c is None else c + 0.001 * estimates[req.skill_id].trust

        best = max(slot, key=score)
        weight = max(r.importance for r in slot) * (1.0 if best.is_core else cfg.optional_weight)
        alts = [catalogue.skills[r.skill_id].name for r in slot if r is not best]
        chosen.append((best, estimates[best.skill_id], alts, weight))

    total_w = sum(w for *_, w in chosen) or 1.0
    known_w = sum(w for _, est, _, w in chosen if est.known)
    match = sum(w * (_coverage(est, req) or 0.0) for req, est, _, w in chosen) / total_w
    upper = sum(w * (c if (c := _coverage(est, req)) is not None else 1.0) for req, est, _, w in chosen) / total_w
    ev_strength = (sum(w * est.trust for _, est, _, w in chosen if est.known) / known_w) if known_w else None

    gapped_ids = {req.skill_id for req, est, _, _ in chosen if est.level is None or est.level < req.required_level}

    gaps: list[SkillGap] = []
    met = gap_n = unknown_n = 0
    for req, est, alts, w in chosen:
        skill = catalogue.skills[req.skill_id]
        cov = _coverage(est, req)
        gap = None if est.level is None else round(max(req.required_level - est.level, 0.0), 2)
        ev_ok = _evidence_met(est, req)

        prereqs = []
        for pid, min_lvl in catalogue.prerequisites.get(req.skill_id, []):
            pe = estimates.get(pid)
            ok = pe is not None and pe.level is not None and pe.level >= min_lvl
            prereqs.append(
                {
                    "skill_id": pid,
                    "skill_name": catalogue.skills[pid].name,
                    "min_level": min_lvl,
                    "estimated_level": pe.level if pe else None,
                    "met": ok,
                }
            )
        unmet_prereqs = [p for p in prereqs if not p["met"]]

        blocking = len(_descendants(graph).get(req.skill_id, set()) & (gapped_ids - {req.skill_id}))
        unlock = 0
        for other in other_roles:
            for oreq in other.requirements:
                if oreq.skill_id == req.skill_id and (est.level is None or est.level < oreq.required_level):
                    unlock += 1
                    break

        if est.level is None:
            unknown_n += 1
            g_norm = cfg.unknown_gap_assumption
            action = "assess"
        elif gap and gap > 0:
            gap_n += 1
            g_norm = gap / req.required_level
            action = "prerequisite" if unmet_prereqs else "learn"
        else:
            met += 1
            g_norm = 0.0
            action = "maintain" if (ev_ok and est.status != "self_reported") else "verify"

        priority = w * g_norm * (1 + cfg.unlock_bonus * unlock) * (1 + cfg.blocking_bonus * blocking)
        if action == "verify":
            priority = w * cfg.verify_weight * (1 + cfg.unlock_bonus * unlock)
        gaps.append(
            SkillGap(
                skill_id=req.skill_id,
                skill_slug=skill.slug,
                skill_name=skill.name,
                category=skill.category,
                required_level=req.required_level,
                estimated_level=est.level,
                status=est.status,
                trust=est.trust,
                gap=gap,
                coverage=None if cov is None else round(cov, 3),
                importance=req.importance,
                weight=round(w, 3),
                is_core=req.is_core,
                evidence_expected=req.evidence_expected,
                evidence_met=ev_ok,
                alt_group=req.alt_group,
                alternatives=alts,
                prerequisites=prereqs,
                blocking_count=blocking,
                unlock_count=unlock,
                priority=round(priority, 4),
                action=action,
                action_text=_action_text(action, skill.name, req, est, unmet_prereqs, alts),
                rationale=req.rationale,
                hypothetical=est.hypothetical,
            )
        )

    gaps.sort(key=lambda g: (-g.priority, g.skill_name))
    return RoleMatch(
        role_id=role.id,
        role_slug=role.slug,
        role_name=role.name,
        role_version=role.version,
        match=round(match, 4),
        match_upper=round(upper, 4),
        known_share=round(known_w / total_w, 4),
        evidence_strength=None if ev_strength is None else round(ev_strength, 3),
        met_count=met,
        gap_count=gap_n,
        unknown_count=unknown_n,
        gaps=gaps,
    )


def _action_text(
    action: str, name: str, req: Requirement, est: SkillEstimate, unmet_prereqs: list[dict[str, Any]], alts: list[str]
) -> str:
    alt = f" (or one of: {', '.join(alts)})" if alts else ""
    if action == "assess":
        return f"Establish a baseline for {name}{alt}: rate yourself or record an assessment."
    if action == "prerequisite":
        names = ", ".join(f"{p['skill_name']} (level {p['min_level']}+)" for p in unmet_prereqs)
        return f"Strengthen prerequisites first: {names}; then work on {name}."
    if action == "learn":
        return f"Raise {name} from level {est.level:g} to {req.required_level}{alt}."
    if action == "verify":
        need = {"assessment": "an assessed result", "project": "project evidence"}.get(
            req.evidence_expected, "project or assessment evidence"
        )
        return f"Your {name} level meets the requirement but is only {est.status.replace('_', ' ')}; add {need}."
    return f"{name} meets the requirement with supporting evidence. Keep it current."


def analyse_all_roles(
    roles: list[RoleInfo],
    estimates: dict[int, SkillEstimate],
    catalogue: Catalogue,
    *,
    config: GapConfig = DEFAULT_CONFIG,
    preferred_role_ids: list[int] | None = None,
) -> list[RoleMatch]:
    graph = _prereq_graph(catalogue)
    preferred = [r for r in roles if r.id in (preferred_role_ids or [])]
    results = [analyse_role(r, estimates, catalogue, config=config, other_roles=preferred, graph=graph) for r in roles]
    results.sort(key=lambda m: (-m.match, -m.match_upper, m.role_name))
    return results


def ranking_sensitivity(
    roles: list[RoleInfo],
    estimates: dict[int, SkillEstimate],
    catalogue: Catalogue,
    *,
    samples: int = 200,
    perturbation: float = 0.2,
    seed: int = 7,
) -> dict[str, Any]:
    """Monte-Carlo robustness of the role ranking to the (expert-judged) weights: every
    importance is multiplied by U(1−p, 1+p) and optional_weight drawn from U(0.3, 0.7)."""
    rng = random.Random(seed)  # noqa: S311 — reproducible Monte-Carlo sampling, not cryptography
    graph = _prereq_graph(catalogue)
    base = analyse_all_roles(roles, estimates, catalogue)
    base_order = [m.role_id for m in base]
    ranks: dict[int, list[int]] = {r.id: [] for r in roles}
    for _ in range(samples):
        perturbed = [
            RoleInfo(
                r.id,
                r.slug,
                r.name,
                r.summary,
                r.description,
                r.version,
                r.source_note,
                tuple(
                    Requirement(
                        q.skill_id,
                        q.required_level,
                        max(0.01, min(1.0, q.importance * rng.uniform(1 - perturbation, 1 + perturbation))),
                        q.is_core,
                        q.evidence_expected,
                        q.alt_group,
                        q.rationale,
                    )
                    for q in r.requirements
                ),
            )
            for r in roles
        ]
        cfg = GapConfig(optional_weight=rng.uniform(0.3, 0.7))
        scored = sorted(
            ((analyse_role(r, estimates, catalogue, config=cfg, graph=graph).match, r.id) for r in perturbed), reverse=True
        )
        for rank, (_, rid) in enumerate(scored, start=1):
            ranks[rid].append(rank)
    out = []
    for rid in base_order:
        rs = ranks[rid]
        out.append(
            {
                "role_id": rid,
                "role_name": next(r.name for r in roles if r.id == rid),
                "base_rank": base_order.index(rid) + 1,
                "best_rank": min(rs),
                "worst_rank": max(rs),
                "p_top1": round(sum(1 for x in rs if x == 1) / samples, 3),
                "p_top3": round(sum(1 for x in rs if x <= 3) / samples, 3),
            }
        )
    top_stability = out[0]["p_top1"] if out else None
    return {
        "samples": samples,
        "perturbation": perturbation,
        "seed": seed,
        "roles": out,
        "top_role_stability": top_stability,
        "interpretation": (
            "Share of weight perturbations in which each role keeps its position. Low stability means the "
            "ranking depends on the exact expert weights and the top roles should be treated as roughly tied."
        ),
    }
