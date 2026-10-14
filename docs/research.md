# Research framing

## Problem

Engineering students lack a trustworthy, individual view of where they stand against concrete role expectations,
what to do next, and how changes would matter. Existing tools usually do one of three things: present a single
opaque "employability score", blur self-claims with demonstrated ability, or use LLMs that state invented facts.

## Contribution

The contribution is an **integrated, evidence-aware career digital twin**:

* versioned student state with evidence-trust semantics, where unknown is not the same as zero;
* a transparent, configurable, sensitivity-tested role-gap model;
* an explainable, calibrated and honestly evaluated readiness classifier with an explicit target definition;
* a what-if simulator that reuses the exact production pipeline on an isolated copy;
* a provenance-aware knowledge graph and an adaptive, prerequisite-ordered roadmap;
* a fully local, access-controlled RAG mentor with structural safeguards against fabrication and injection.

The research value lies in this integration and its evaluation, not in the chatbot or the 3D visuals.

## Research questions

* **RQ1 (validity):** How well do evidence-weighted skill estimates agree with mentor-assessed proficiency, and how
  much does self-rating inflate them?
* **RQ2 (prediction):** On real, consented assessor labels, how well does the readiness model discriminate and stay
  calibrated? Does it beat the rule-based framework match as a predictor?
* **RQ3 (usefulness):** Do students find the gap explanations, simulations and roadmaps useful and understandable
  (SUS, task success, rated usefulness)?
* **RQ4 (progress):** Over one semester, do recorded competencies change, and is roadmap engagement *associated*
  with that change? This is observational, so causal claims are excluded.
* **RQ5 (mentor):** How grounded and safe are local-LLM answers on a held-out question set? Measures: citation
  correctness, fabricated facts, links, and injection resistance.

## What is measured vs designed vs simulated (current state)

| Kind | Items |
|---|---|
| **Measured** (executed in this repository) | 94 backend and 25 frontend automated tests; 6 Playwright end-to-end journeys (dev servers and containers); ML evaluation on synthetic data ([model card](ml/model-card.md)); RAG evaluation on a small in-house set ([report](reports/rag-evaluation.md)); local LLM benchmark ([json](reports/llm-benchmark.json)); backup and restore check; link validation of 50 resources |
| **Engineering design choices** | proficiency trust weights, %→level mapping, gap formula constants, roadmap effort ranges, role weights, band thresholds |
| **Simulated** | the entire training/evaluation cohort of the active readiness model |
| **Not yet measured** | anything about real students, the usefulness of recommendations, fairness on real populations |

## Proposed ethical pilot (not yet conducted)

* **Approval and consent:** institutional ethics approval; opt-in students; research-use consent captured in-app
  and revocable; a data protection impact assessment; no protected attributes.
* **Design:** one semester, 40–80 volunteers.
  * Baseline: mentor-recorded assessments (DSA, SQL, communication) plus an assessor readiness label.
  * Monthly check-ins.
  * End-of-semester repeat assessments and label.
* **Instruments:** SUS questionnaire; in-app usefulness ratings (already implemented); task-based usability
  sessions; mentor interviews.
* **Analysis:**
  * RQ1: agreement between self-rating and assessment (weighted κ).
  * RQ2: grouped cross-validation on real labels (same pipeline).
  * RQ4: mixed-effects models of competency change. Associations only, with no control group, so no causal
    claims.
* **Stopping rules:** pause if any student reports harm or distress, or if a data-protection issue is found.

## Threats to validity

The role framework weights are expert judgements; the model is trained on synthetic data; the RAG evaluation set
was written by the developers; the pilot sample is likely self-selected; and assessor labels may differ between
assessors (so inter-rater agreement should be measured).
