# RAG evaluation — method, results and iteration history

The latest machine-generated report is [`rag-eval.md`](rag-eval.md) (JSON: `rag-eval.json`). It includes every
generated answer for human review. Re-run with `cd backend && uv run python -m eval.run_rag_eval`. It uses the test
database and a temporary data directory.

## Set-up

* **Models:** `qwen3:8b` (Q4_K_M, thinking disabled, 4,096-token context) and `nomic-embed-text` (768-d), both
  local via Ollama 0.40 on an RTX 4060 Laptop GPU.
* **Knowledge base:** 7 authored documents plus 6 role guides generated from the live catalogue, giving 13
  documents and 78 chunks.
* **Evaluation set** (`backend/eval/rag_eval_set.json`, v2): 24 retrieval questions with expected source
  documents, and 9 end-to-end generation scenarios with automated pass criteria. The scenarios cover grounded
  citation, fabricated predictions, fabricated facts, role facts, guarantee language, prompt injection in an
  uploaded document, cross-user isolation, out-of-scope refusal, and citation/link validity.

## Results history

| Run | Change | Retrieval hit@1 / hit@3 / MRR | Generation |
|---|---|---|---|
| 1 (baseline) | — | 0.917 / 0.958 / 0.938 | 7/8 — G01 paraphrased "level 2" instead of using the scale's term |
| 2 | Contextual chunk headers (title + section embedded with each chunk); "keep exact terms" rule | 1.000 / 1.000 / 1.000 | 8/8 |
| 3 | Manual review: model claimed an injected resume "has no skills listed". Added the uploaded-document list with withheld-passage counts, and catalogue resources, to the student context | 1.000 / 1.000 / 1.000 | 8/8; G06 now says passages were withheld |
| 4 | Manual review: catalogue resources were given `[S#]` citations. Tightened citation rule; added G09 (citation validity) | 1.000 / 1.000 / 1.000 | 9/9 |
| 5 (current) | Manual review: the model wrote **invented URLs** for real resources. Added catalogue URLs to context, a "never write other URLs" rule, and **server-side removal of any non-catalogue link** before storage/display | 1.000 / 1.000 / 1.000 | 9/9; 0 links needed removal in this run |

## Honest interpretation

* The eval set is **small and was written by the same team that tuned the system**, and runs 2–5 were partly
  motivated by failures on this same set. The perfect retrieval scores are therefore optimistic. A held-out
  question set written by someone else (for example pilot students' real questions) is required before claiming
  retrieval quality.
* Automated checks are coarse (string and regex criteria). They catch specific failure modes, not answer quality.
  The answers are in `rag-eval.md` for human review.
* Manual review also found **residual minor inaccuracies** not caught by the checks. For example, one answer
  suggested self-rating "on a scale of 1–10" (the app uses 0–4). Students should treat mentor output as advice
  and verify it.
* Structural guarantees hold regardless of model behaviour, because they do not depend on the LLM. These are
  owner-scoped retrieval, injection-flagged passages never reaching the model, no tool access, and removal of
  non-catalogue links. They are covered by unit tests.

## Latency (from the same runs)

Median end-to-end answer time across scenarios was 3–5 s warm (retrieval, context assembly and generation of
about 150–350 tokens). The first request after the model is unloaded adds 8–22 s of load time. See
`llm-benchmark.json` for controlled measurements.
