# Methodology

The AI Career Guidance App separates four questions that are easy to conflate. Each has its own documented method.

| Question | Component | Method | Never claims |
|---|---|---|---|
| What can the student demonstrably do? | Proficiency estimation | highest-trust evidence wins (below) | that a self-rating or an uploaded certificate proves skill |
| How does the profile compare with a role? | Role match & skill gaps | transparent weighted formula | a probability of being hired |
| Would an assessor judge the student interview-ready? | Readiness model | versioned ML classifier ([model card](../ml/model-card.md)) | placement or employment outcomes |
| What should the student do next? | Roadmap | prerequisite-ordered plan from gaps | that completing a resource proves mastery |

## 1. Proficiency scale and evidence trust

Scale 0–4: None · Awareness · Working · Proficient · Advanced (definitions in `knowledge/proficiency-scale.md`).

| Source | Trust | How the level is set |
|---|---:|---|
| Verified assessment (mentor-recorded) | 1.00 | percentage ÷ 25, capped at 4 (a documented heuristic, not psychometric calibration); latest result per assessment, averaged across assessments that measure the skill |
| Evidence on a verified project/experience/certificate | 0.85 | highest claimed level |
| Evidence on an unverified/pending source | 0.60 | highest claimed level |
| Self-rating | 0.40 | the rating |
| Nothing recorded | 0 | **unknown** — shown as unmeasured, never as zero |

The highest-trust available source determines the estimate. Lower-trust signals are still shown for transparency.
Editing the content of a verified item resets it to unverified.

## 2. Role match and skill-gap formula

Each role has a versioned specification. Every requirement has a skill, a required level *L*, an importance in
(0, 1], core or optional, an evidence expectation (any, project or assessment) and a written rationale.
Alternatives (for example "one of Python, Java or C++") are grouped, and the best-covered member counts.
Provenance: [`role-framework.md`](role-framework.md).

```
W_k        = importance_k × (1 if core else optional_weight)          optional_weight default 0.5
coverage_k = min(E_k / L_k, 1)                                          E_k = estimated level
match      = Σ W·coverage (unknown → 0) / Σ W                           "demonstrated"
match_upper= Σ W·(coverage, unknown → 1) / Σ W                          "if every unknown were met"
priority_k = W_k × (gap_k / L_k) × (1 + β·U_k) × (1 + γ·B_k)            β = 0.15, γ = 0.20
             unknown skills use gap/L = 0.5 and the action "assess"
```

*U* is the number of other preferred roles that also need the skill above the current level. *B* is the number of
other gap skills that depend on it, directly or transitively. Every constant is adjustable in the skill-gap screen
and the API, and the defaults are documented choices.

**Ranking sensitivity.** 200 Monte-Carlo samples multiply every importance by U(0.8, 1.2) and draw the optional
weight from U(0.3, 0.7). Each role's rank range and P(top 1/top 3) are reported, so fragile rankings are visible.
The seed is fixed, so results are reproducible.

## 3. What-if simulation

The student's real state is loaded and deep-copied, and only the requested inputs are changed. The **same**
estimation, feature, validation, model and gap code then runs on the copy. Hypothetical skill levels are treated
as if assessed. Implausible jumps are flagged (for example +2 levels, or more than 1.0 CGPA point), and invalid
values are rejected (for example moving to an earlier semester). Nothing is persisted unless the student saves the
scenario, and saving stores only the scenario, never the profile. Differences are model outputs, **not causal effects**.

## 4. Roadmap generation (`roadmap-v1`)

1. Take actionable gaps for the target role (learn / prerequisite / assess / verify) in priority order.
2. Insert unmet prerequisites (recursively) before the skills they unlock. A prerequisite inherits the priority
   of what it unlocks.
3. Order with a priority-aware topological sort over the prerequisite graph.
4. Effort is a planning range per level step: 5–10 h to reach level 1, 10–20 h for level 2, 20–40 h for level 3 and
   40–80 h for level 4. Assess items take 2–4 h and verify items 4–10 h. Items are scheduled sequentially against
   the student's weekly hours.
5. Attach the best catalogue resource for each item, preferring a verified link, the right level and free access.
   URLs are never invented. Unverified links are labelled.
6. Regeneration archives the old plan, carries progress over for the same skill and action, and records a diff.
   The plan is marked stale when the twin or the role version changes.

## 5. Knowledge graph

Built with NetworkX from stored data. Node types are student, skill, role, resource, assessment and project. Every
edge carries provenance: `framework`, `evidence`, `self_reported` or `inferred`. Inferred edges, such as "likely
has prerequisite X because X's dependent was demonstrated at level 3 or above with evidence", are visually distinct
and labelled as inferences. Supported queries include blocking prerequisites, resources for top gaps,
alternative roles by overlap, and skills that unlock several roles.

NetworkX is sufficient at this scale (tens of roles, hundreds of nodes), so Neo4j was not introduced. It would be
justified if graph queries needed to span many students at once, or exceeded in-memory sizes.
