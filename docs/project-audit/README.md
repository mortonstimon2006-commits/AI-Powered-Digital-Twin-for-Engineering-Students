# Project audit — AI Career Guidance App (formerly TwinPath AI)

An evidence-based audit of the whole repository, written to explain the project from beginner to advanced level
and to state honestly what is implemented, verified, partial or missing.

**Audited version:** commit `b2fae2a` on `main` (2026-10-21), plus the audit documents themselves.
**Naming:** the product was renamed from *TwinPath AI* to *AI Career Guidance App*, and the AI mentor to *Personalized
Mentor*. Internal identifiers were deliberately left unchanged (`twinpath_app` database role, `TWINPATH_ENV`,
`tp_session`/`tp_csrf` cookies, `X-Requested-With: twinpath`, `twinpath.*` logger names, container names), so they
appear in code citations below.

## How to read the evidence

| Label | Meaning |
|---|---|
| `path:line` or `path` L*n* | A location in the code that supports the statement. Line numbers refer to commit `b2fae2a`. |
| **Audit run (2026-10-21)** | A command executed during this audit, with its result. |
| **Historical** | A result recorded earlier in a report file and not re-run during this audit. |
| *Illustrative* | A worked example with invented numbers, used only for teaching. Never a project result. |
| **NOT VERIFIED** | Implemented or documented, but not demonstrated in a running environment during this audit. |

## Documents

| # | File | Contents |
|---|---|---|
| 00 | [Executive summary](00-executive-summary.md) | Purpose, users, capabilities, verified results, key findings, limitations |
| 01 | [Complete file inventory](01-complete-file-inventory.md) | All 238 tracked files with purpose, symbols, dependencies and status |
| 02 | [System architecture](02-system-architecture.md) | Components, Mermaid architecture and sequence diagrams, data flows |
| 03 | [Backend code walkthrough](03-backend-code-walkthrough.md) | Request lifecycle, every module, all 124 API operations |
| 04 | [Frontend code walkthrough](04-frontend-code-walkthrough.md) | Routing, API client, state, every page, accessibility, a full trace |
| 05 | [Machine learning deep dive](05-machine-learning-deep-dive.md) | Problem, synthetic data, algorithms, training, calibration, SHAP, OOD, registry |
| 06 | [LLM and Ollama deep dive](06-llm-and-ollama-deep-dive.md) | LLM fundamentals and the exact local-inference integration |
| 07 | [RAG pipeline deep dive](07-rag-pipeline-deep-dive.md) | Ingestion, chunking, embeddings, Chroma, retrieval, prompting, safety, evaluation |
| 08 | [Digital twin, roles and simulator](08-digital-twin-roles-and-simulator.md) | Evidence trust, snapshots, gap formula, what-if simulation |
| 09 | [Knowledge graph and roadmap](09-knowledge-graph-and-roadmap.md) | Graph model and queries, roadmap generation and regeneration |
| 10 | [Database and data model](10-database-and-data-model.md) | 36 tables, ER diagram, constraints, row-level security, lifecycle |
| 11 | [Security review](11-security-review.md) | Each control: threat, implementation, evidence, gaps |
| 12 | [Docker, environment and deployment](12-docker-environment-and-deployment.md) | Native, container and hosted modes with exact commands |
| 13 | [Testing and quality assurance](13-testing-and-quality-assurance.md) | Suites, commands, results of this audit, coverage gaps |
| 14 | [Resume and job-description processing](14-resume-and-job-description-processing.md) | Upload safety, parsing, skill extraction, comparison |
| 15 | [Project progress report](15-project-progress-report.md) | Implemented / partial / missing, prioritised recommendations |
| 16 | [Presentation and viva guide](16-presentation-and-viva-guide.md) | 2- and 5-minute explanations, 72 viva questions, hard questions |

The original audit prompt was cut off after deliverable `10-dat…`; files 10–16 follow the remaining phases of that
prompt (database, security, deployment, testing, resume/JD, progress report, presentation).
