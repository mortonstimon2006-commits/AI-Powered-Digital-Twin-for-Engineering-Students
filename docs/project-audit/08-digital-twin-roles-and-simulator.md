# 08 — Digital twin, role matching and the what-if simulator

## 1. The digital twin

A **digital twin** is a living, versioned digital representation of something real. Here it represents one
student's career profile:

| Part | Table(s) | Notes |
|---|---|---|
| Academic record and goals | `student_profiles`, `student_role_preferences` | Degree, specialisation, semester (1–12), graduation year, CGPA (0–10), attendance **only with the `attendance_data` consent**, interests, learning preferences, weekly hours (1–80), target role, up to 5 ranked preferred roles |
| Skills on a 0–4 scale | `student_skills` | Self-ratings. **No row = unknown, never 0** (`models/twin.py` L75–76) |
| Projects, experience, certifications | `projects`, `experiences`, `certifications` | Each has `verification_status` ∈ unverified / pending / verified / rejected; URLs must be `https://` (DB CHECK) |
| Skill evidence | `skill_evidence` | Links a skill to exactly one project, experience or certification at a claimed level 1–4 (a CHECK constraint enforces exactly one source) |
| Assessments | `assessment_results` | `source` ∈ mentor_recorded / self_reported / imported; self-reported results start unverified |
| Versions | `twin_snapshots` | Content-addressed snapshots (§3) |
| Assessor labels | `readiness_labels` | Supervised target for future training, frozen to a snapshot |

In memory, a twin is a `TwinState` (`backend/app/services/twin/state.py` L86–124): plain dataclasses for the
profile, self-ratings, evidence, assessments, projects, experiences, certifications and simulator-only
`hypothetical_levels`. `load_twin_state` (L133–210) fills it with queries that each filter `user_id` explicitly;
row-level security is the second line of defence.

## 2. Evidence provenance: not all claims are equal

Saying "I know SQL", linking a project that used SQL, and passing a mentor-recorded SQL assessment are different
strengths of evidence. The implementation encodes that explicitly (`backend/app/services/twin/proficiency.py`).

| Status (best first) | Source | Trust weight | How the level is derived |
|---|---|---|---|
| `assessed` | Latest **verified** result per assessment, mapped to the skills that assessment measures (`assessment_skills`) | 1.00 | `pct_to_level(pct) = clamp(pct / 25, 0, 4)` (L34–37); several assessments → **average** |
| `verified_evidence` | Evidence attached to a project/experience/certification a mentor **verified** | 0.85 | **max** claimed level among such evidence |
| `unverified_evidence` | Evidence attached to an unverified or pending item (**rejected** items are ignored) | 0.60 | max claimed level |
| `self_reported` | The student's rating | 0.40 | the rating |
| `unknown` | Nothing | 0.00 | `level = None` |

`estimate_skills` (L54–133) collects every signal per skill and takes the **highest-trust status present**
(`STATUS_ORDER`, L31). Lower-trust signals are kept in `signals` for transparency but don't override. So:

* a verified assessment always wins over a higher self-rating;
* a skill nobody has said anything about stays *unknown*; it isn't treated as level 0.

**Example (illustrative):** a student self-rates SQL at 3, links SQL at level 2 in an *unverified* project, and has a
*verified* SQL assessment at 60%. The estimate is `assessed`, level 60/25 = **2.4**, trust 1.0. The self-rating of 3
is shown as a weaker signal. Tested by `test_unknown_vs_self_reported_vs_evidence_precedence`.

**Limitation:** the 25-points-per-level mapping and the trust weights are documented heuristics, not psychometrically
calibrated.

## 3. Snapshots, versions and diffs

`ensure_snapshot(db, user_id, reason)` (`backend/app/services/twin/history.py` L18–40):

1. Load the `TwinState` and compute `content_hash = SHA-256(canonical, sorted JSON)` (`state.py` L122–124).
2. If the latest snapshot has the same hash, return it: **no duplicate versions**.
3. Otherwise insert `twin_snapshots(version = previous + 1, reason, content_hash, state = full JSON, features = the
   19 ML features)` and set `student_profiles.twin_version`.

Snapshots are taken on every twin change (`_commit_change`, `api/v1/twin.py` L97–99), on mentor verification, on
readiness analysis, when a scenario is saved, and when an assessor label is recorded.

**What history preserves:** the complete serialised twin and its feature vector at each version, with the reason.
Predictions, labels and scenarios point to the exact `snapshot_id` they used, so every past estimate can be traced
to its inputs.

**Diffs:** `diff_states` (L115–167) produces human-readable changes between two versions:

* profile field changes;
* self-rating changes;
* added or removed projects, experiences and certifications;
* verification status changes;
* added or removed evidence;
* new assessments.

`feature_deltas` (L170–176) lists changed model inputs. Both are served by `GET /api/v1/twin/diff` and shown in the
History section. Tested by `test_profile_update_creates_versioned_snapshots`.

**Completeness** (`completeness`, L59–109): a weighted score that guides the student. It isn't used by the model.

| Section | Weight | Full when |
|---|---|---|
| Academic | 0.20 | degree, specialisation, semester, graduation year, CGPA all present |
| Goals | 0.15 | target role (0.6) + career interests (0.4) |
| Skills | 0.20 | ≥ 8 skills rated |
| Evidence | 0.20 | projects + linked evidence (up to 6) |
| Assessments | 0.15 | ≥ 2 verified assessments |
| Preferences | 0.10 | learning preferences + weekly hours |

## 4. Verification workflow

1. The student adds an item (initially `unverified`) and requests verification → `pending`
   (`POST /api/v1/twin/verification-requests`, `twin.py` L499–510).
2. An assigned mentor with the student's `mentor_sharing` consent sets `verified` or `rejected`, recording
   `verified_by` and `verified_at` (`POST /api/v1/staff/students/{id}/verify`, `staff.py` L196–219).
3. If the student later **edits** a verified item, it returns to `unverified` (`test_verified_item_edit_resets_verification`).
4. Mentors can also record **verified assessment results** directly (`POST /staff/students/{id}/assessments`).

There's no automatic verification: links to GitHub or certificates are stored, but checking them is a mentor's
decision.

## 5. Role specifications

Six roles: AI/ML Engineer, Backend Developer, Data Analyst, Data Scientist, Full-Stack Developer and Software
Developer. They have **91 requirements** over 42 skills (`backend/app/seed/catalogue_data.py`). Each requirement
(`RoleSkillRequirement`; the in-memory `Requirement` is in `services/catalogue.py` L41–49) has:

* `required_level` 1–4;
* `importance` (an expert-judged weight);
* `is_core` (core vs optional);
* `evidence_expected` ∈ any / project / assessment;
* `alt_group`: requirements in the same group are alternatives, e.g. *any one* backend language;
* `rationale`.

**Versioning:** admin edits increment the role's `version` and store a full copy in `role_versions`
(`snapshot_role_version`, used at `admin.py` L323 and L340). Roadmaps record the role version they were built from
and are flagged *stale* when it changes. Test: `test_role_versioning_and_staleness`.

**Provenance:** the framework was authored by the project team as an engineering synthesis of common entry-level
expectations. It isn't derived from a job-postings dataset, and its weights aren't empirically validated
(`FRAMEWORK_SOURCE_NOTE`; `docs/methodology/role-framework.md`).

## 6. The gap formula (exact implementation)

`analyse_role` (`backend/app/services/career/gap_engine.py` L158–282). First, requirements in the same `alt_group`
collapse into one **slot**, represented by the best-covered member (`_slots`, L126–137; the best is chosen by
coverage, with trust as a tie-breaker, L174–178).

For each slot *k*, with required level *L_k*, estimate *E_k* (None if unknown) and trust *t_k*:

$$W_k = \text{importance}_k \times \begin{cases}1 & \text{core}\\ \text{optional\_weight} \ (0.5) & \text{optional}\end{cases}$$
$$\text{coverage}_k = \min(E_k / L_k,\ 1) \qquad \text{gap}_k = \max(L_k - E_k,\ 0)$$

$$\text{match} = \frac{\sum_k W_k\cdot\text{coverage}_k \ (\text{unknown}\to 0)}{\sum_k W_k}\qquad
\text{match\_upper} = \frac{\sum_k W_k\cdot(\text{coverage}_k \text{ or } 1 \text{ if unknown})}{\sum_k W_k}$$

$$\text{known\_share} = \frac{\sum_{k\ \text{known}} W_k}{\sum_k W_k}\qquad
\text{evidence\_strength} = \frac{\sum_{k\ \text{known}} W_k\, t_k}{\sum_{k\ \text{known}} W_k}$$

**Priority** of working on slot *k*:

$$\text{priority}_k = W_k \cdot g_k \cdot (1 + \beta\, U_k)\cdot(1 + \gamma\, B_k)$$

where:

* *g_k* = gap_k / L_k, or 0.5 (`unknown_gap_assumption`) if unknown;
* *U_k* = number of the student's *other preferred roles* that also need this skill above the current level
  (β = `unlock_bonus` = 0.15);
* *B_k* = number of other gapped skills in this role that transitively depend on this skill in the prerequisite graph
  (γ = `blocking_bonus` = 0.2).

Skills that already meet the level but rely only on self-rating, or lack the expected evidence, get a "verify"
priority of W_k × 0.3 × (1 + β·U_k) (L235–237).

**Actions** (L222–233):

| Action | When |
|---|---|
| `assess` | unknown |
| `prerequisite` | gap > 0 and a prerequisite is below its minimum level |
| `learn` | gap > 0 |
| `maintain` | met with the expected evidence |
| `verify` | met but evidence is weaker than expected |

Each action comes with a generated sentence (`_action_text`, L285–301).

`match` is the *demonstrated* coverage (unknown counts as 0). `match_upper` is the optimistic bound (unknown counts as
met). The truth lies between them, and the gap between the two shows how much is still unknown.

**Configurable:** `GET /api/v1/skill-gaps/roles/{id}` accepts `optional_weight`, `unlock_bonus`, `blocking_bonus` and
`unknown_gap_assumption` (each 0–1, `career.py` L222–230). These are the sliders on the Skill gaps page;
`verify_weight` is fixed at 0.3.

### Worked example (illustrative)

A role with three core requirements, each of importance 1.0:

| Skill | L | E | coverage | gap | g |
|---|---|---|---|---|---|
| Python | 3 | 3.0 (assessed) | 1.00 | 0 | 0 |
| SQL | 3 | 2.0 (self-reported) | 0.67 | 1.0 | 0.33 |
| HTTP | 3 | unknown | — | — | 0.5 (assumed) |

* match = (1·1.00 + 1·0.67 + 1·0) / 3 = **0.556**
* match_upper = (1 + 0.67 + 1) / 3 = **0.889**
* known_share = 2/3
* evidence_strength = (1.0 + 0.4)/2 = 0.70
* If SQL is a prerequisite of one other gapped skill (B = 1) and isn't needed by other roles (U = 0):
  priority_SQL = 1 × 0.33 × 1 × 1.2 = **0.40**
* priority_HTTP (unknown) = 1 × 0.5 = **0.50** → HTTP is ranked first, with action "assess"
  (establish a baseline).

Properties tested: `test_match_bounds_and_unknown_is_not_zero`, `test_alternative_group_uses_best_member`,
`test_prerequisite_action_and_priority_ordering`, `test_optional_weight_is_configurable`,
`test_verify_action_for_self_reported_only`.

### Role ranking and its sensitivity

`analyse_all_roles` (L304–316) sorts roles by match, then match_upper. Because the weights are expert judgements,
`ranking_sensitivity` (L319–391) runs a **Monte-Carlo test**:

* 200 samples with a fixed seed (7);
* every importance is multiplied by a random factor in [0.8, 1.2];
* `optional_weight` is drawn from [0.3, 0.7];
* for each role it reports best and worst rank and the probability of staying top-1 and top-3.

Low stability means the top roles should be treated as roughly tied. Reproducibility is tested by
`test_sensitivity_is_reproducible`.

**Not a hiring probability.** Every gap response carries the disclaimer "A profile-to-framework match, not a
probability of being hired."

## 7. The what-if simulator

### How a hypothetical change is represented

`ScenarioChanges` (`backend/app/services/career/simulator.py` L51–73), a strict Pydantic model:

* `skill_levels`: up to 20 `{skill_id, level 0–4, basis: "assessed" | "project_evidence"}`;
* `add_projects` (0–10), `add_deployed_projects` (≤ `add_projects`), `add_internship_months` (0–24),
  `add_verified_certifications` (0–10), `add_hackathons` (0–10);
* `assessments`: up to 3 `{kind: coding | communication | mock_interview, pct 0–100}`;
* `cgpa` (0–10), `semester` (1–12).

Validation rejects duplicate skills or assessment kinds, deployed > added projects, unknown skill ids, a semester
earlier than the current one, and an empty scenario (all 422).

### How the real twin is protected

`simulate` (L198–281):

1. `baseline = load_twin_state(db, user_id)`: a **read-only** load.
2. `apply_changes` (L81–174) starts with `state = base.clone()`, a **deep copy** (`copy.deepcopy`, `state.py`
   L99–100). Every change is applied to the copy and tagged `hypothetical=True`:
   * skill levels go into `hypothetical_levels`, treated as *assessed*;
   * project evidence is added as *verified* hypothetical evidence;
   * simulated assessments are dated 9999-12-31 so they count as the latest.
3. The **same functions** run on both states: `estimate_skills`, `build_features` (same validation), `analyse_role`
   for up to 4 roles, and `predict` with the same active model.
4. The function writes nothing. The response lists `changes_applied`, `plausibility_notes`, `feature_changes`,
   baseline vs hypothetical readiness (band, calibrated score, top factors, warnings) and per-role match deltas with
   changed skills.

Isolation is tested by `test_simulation_never_touches_real_twin` (the twin's content hash and snapshot count are
unchanged after simulating).

**Plausibility notes** flag a skill jump of ≥ 2 levels ("usually takes several months of work") and a CGPA change of
more than 1.0. They warn; they don't block.

### Worked example (illustrative)

*"What might happen if I improve Python from level 2 to level 4 and complete a backend project?"*

```json
POST /api/v1/simulations/run
{"changes": {"skill_levels": [{"skill_id": <python id>, "level": 4, "basis": "assessed"}],
             "add_projects": 1, "add_deployed_projects": 1},
 "role_ids": [<backend developer id>]}
```

* Python's hypothetical estimate becomes 4.0 (status *assessed*, flagged hypothetical). A plausibility note says a
  2-level jump usually takes months.
* Features change: `lvl_programming` rises (if Python is the programming category's main known skill),
  `evidence_strength` rises (one more strongly evidenced skill), `projects` +1, `deployed_projects` +1.
* The Backend Developer match rises if Python is in its requirements; changed skills list Python 2 → 4, action
  `learn` → `maintain`.
* Readiness: the same model scores both vectors. The band might move from *Developing* to *Likely interview-ready*.

**What this means:** under the current model and framework, this profile change is *associated* with that output
change. It doesn't mean doing those things would make the student employable, or even readier in an assessor's eyes.
The response always includes the three limitations at L275–279.

### Saving and comparing scenarios

`POST /api/v1/simulations/scenarios` (`career.py` L314–334) recomputes the result and stores it in
`what_if_scenarios` with:

* the scenario name;
* `changes` (the exact request);
* `result`;
* `base_snapshot_id` (the twin version it started from);
* `model_version_id`.

Limit: 50 per student. Scenarios are private (`test_saved_scenarios_are_private`) and are listed on the Simulator
page. The mentor can reference the latest saved scenario when a question mentions "what if".

## Reproducibility

| Question | Answer |
|---|---|
| Are inputs stored? | Yes: the exact request (`changes`) and the base snapshot id |
| Is the model version stored? | Yes: `model_version_id` |
| Can a saved scenario be re-run against its original snapshot automatically? | **No.** There's no replay endpoint. `simulate` always loads the *current* twin. A replay would need the stored snapshot's `state` (available as JSON) passed through `TwinState.from_json` (`state.py` L108–120, already implemented) and the recorded model version (still loadable if the artifact is kept). That's straightforward to add, but it doesn't exist |
| Are results deterministic? | Yes for a given twin, catalogue and model: the pipeline has no randomness at inference |

So saved scenarios are **traceable** (you can see exactly what was asked and against which version), but not
automatically **reproducible**.
