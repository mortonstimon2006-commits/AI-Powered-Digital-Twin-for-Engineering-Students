---
title: How the AI Career Guidance App works — methodology and limitations
---

# How the AI Career Guidance App works

The AI Career Guidance App keeps a digital twin of each student: a structured, versioned record of academic details, skills, practical evidence (projects, internships, certifications), assessments and goals. Several independent components read this twin. Each one answers a different question, and none of them predicts whether a student will be hired.

## Skill estimates and evidence trust

Every skill estimate comes from the highest-trust source available:

- **Assessed** (highest trust): a verified assessment result recorded by a mentor. A percentage score is mapped to the 0–4 scale at 25 percentage points per level. This mapping is a documented heuristic, not a psychometric calibration.
- **Verified evidence**: a project, internship or certification that a mentor has verified, linked to the skill at a claimed level.
- **Unverified evidence**: the same kind of evidence that has not yet been verified.
- **Self-reported** (lowest trust): the student's own rating.
- **Unknown**: nothing recorded. Unknown is never treated as zero proficiency. It means "not yet measured".

A GitHub link or an uploaded certificate is not proof of competence by itself. It becomes stronger evidence only after verification.

## Role match and skill gaps

Each career role has a versioned requirement specification: required skills, the expected proficiency level, an importance weight, whether the skill is core or optional, and what kind of evidence is expected. The specification was written by the project team as an engineering synthesis of common entry-level expectations. It was not derived from a job-postings dataset, and the weights are expert judgements awaiting validation.

The **match score** is the importance-weighted share of requirements the student currently meets. Unknown skills count as "not demonstrated", so the score is reported together with an **upper bound**: the score the student would have if every unknown skill turned out to meet its requirement. The match score compares a profile with a framework. It is **not** a probability of being hired.

Gaps are prioritised by importance × relative gap size, with small bonuses when a skill is a prerequisite for other missing skills or is needed by the student's other preferred roles. The bonuses and the optional-skill weight are configurable, and a sensitivity analysis shows how stable the role ranking is when the weights change.

## Readiness model

The readiness model is a machine-learning classifier. It estimates whether a qualified assessor would judge the student ready to interview for an entry-level technical role. Its inputs are features computed from the twin: CGPA, semester, category skill levels, evidence strength, projects, internship months, verified certifications, hackathons and verified assessment scores.

Important limitations:

- The model predicts an **assessor's judgement**, not placement or employment.
- If the active model was trained on synthetic development data, its numbers are a demonstration of the method only.
- A probability is shown only when the model's calibration has been validated on held-out data; otherwise only a band is shown.
- Explanations (SHAP attributions) describe how the model used each input. They are associations learned from training data, not causes.

## What-if simulator

The simulator copies the student's twin, changes only the selected inputs, and re-runs the same model and gap engine. Nothing is saved to the real profile. A change in the simulated estimate does not prove that the real action would cause the same change in employability.

## Roadmaps

Roadmaps are generated from the current skill gaps for a target role. Prerequisites are ordered first, and the plan is scheduled against the student's weekly study hours. Effort ranges are planning estimates. Completing a roadmap item does not raise a skill estimate by itself; mastery must be shown through evidence or a verified assessment.

## The Personalized Mentor

The Personalized Mentor runs a language model **locally** through Ollama. Prompts and student data are not sent to any external AI service. The Personalized Mentor receives a summary of the student's twin from the app's database, plus passages retrieved from this knowledge base and the student's own uploaded documents. It is instructed never to invent scores, skills, job openings or outcomes, and to say when information is not recorded. Its advice is generated text and can still be wrong, so important decisions should be discussed with a human mentor.
