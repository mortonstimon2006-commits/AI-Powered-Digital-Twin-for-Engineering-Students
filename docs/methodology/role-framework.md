# Role-skill framework (v1) — provenance and limitations

* **What it is:** six entry-level role specifications (AI/ML Engineer, Data Analyst, Data Scientist, Software
  Developer, Backend Developer, Full-Stack Developer). Together they contain 91 weighted requirements over 42
  skills, linked by 33 prerequisite relationships. The source data is `backend/app/seed/catalogue_data.py`.
* **How it was produced:** an engineering synthesis by the project team of commonly stated entry-level
  expectations for each role.
* **What it is not:** it is **not** derived from a statistical analysis of job postings, and the importance weights
  are **expert judgements awaiting validation**.
* **Versioning:** every administrator edit increments the role version and stores an immutable snapshot in
  `role_versions`. Gap analyses and roadmaps record the version they used, and students' plans are flagged stale
  when it changes.
* **Validation plan (not yet done):**
  1. Review by at least two faculty members and two industry practitioners per role.
  2. Inter-rater agreement on required levels.
  3. Compare against a documented, licensed sample of job descriptions using the built-in JD parser.
  4. Record revisions in `source_note`.
* **Sensitivity:** the role-ranking stability analysis (Methodology §2) exists precisely because the weights are
  uncertain.

Learning resources: 50 catalogued resources, all free or freemium, from official documentation and established
open courses. A live SSRF-guarded check on 2026-10-14 found 47 verified, 2 that refuse automated checks (labelled
"unverified") and 1 broken (replaced with a verified URL). Effort estimates are the team's planning ranges.
