"""Deterministic resume / job-description analysis against the skill catalogue.

Everything extracted is a SUGGESTION: skills found in a resume are shown as unconfirmed until
the student confirms them (and even then they count only as self-reported). Contact details
are detected only to exclude them; they are never stored in the analysis.
"""

from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache
from typing import Any

from app.services.catalogue import Catalogue

SECTION_PATTERNS = {
    "summary": r"(professional )?summary|objective|profile|about me",
    "education": r"education|academic (details|background|qualifications?)",
    "experience": r"(work |professional )?experience|internships?|employment( history)?",
    "projects": r"(academic |personal |key )?projects?",
    "skills": r"(technical |key |core )?skills|technologies|tech stack|tools",
    "certifications": r"certifications?|courses|licen[cs]es",
    "achievements": r"achievements|awards|honou?rs|accomplishments",
    "activities": r"(extra[- ]?curricular )?activities|leadership|volunteering|hackathons?",
    "publications": r"publications|research",
}
_SECTION_RES = {k: re.compile(rf"^\s*(?:{v})\s*:?\s*$", re.I) for k, v in SECTION_PATTERNS.items()}
WEAK_STARTS = ("worked on", "helped", "responsible for", "did ", "was involved", "participated in", "assisted")
ACTION_VERBS = (
    "built",
    "designed",
    "implemented",
    "developed",
    "analysed",
    "analyzed",
    "automated",
    "optimised",
    "optimized",
    "deployed",
    "created",
    "led",
    "reduced",
    "improved",
    "trained",
    "evaluated",
    "migrated",
)
URL_RE = re.compile(r"https?://\S+|(?:github|gitlab|linkedin)\.com/\S+", re.I)


@lru_cache(maxsize=4)
def _alias_patterns(fingerprint: str, aliases: tuple[tuple[int, str], ...]) -> list[tuple[int, str, re.Pattern[str]]]:
    out = []
    for sid, alias in aliases:
        if len(alias) < 2:
            continue
        pat = re.compile(rf"(?<![A-Za-z0-9+#]){re.escape(alias)}(?![A-Za-z0-9+#])", re.I)
        out.append((sid, alias, pat))
    return out


def _patterns(catalogue: Catalogue) -> list[tuple[int, str, re.Pattern[str]]]:
    pairs = []
    for s in catalogue.skills.values():
        for a in {*s.aliases, s.name.lower()}:
            pairs.append((s.id, a))
    return _alias_patterns(catalogue.fingerprint, tuple(sorted(pairs)))


def split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"_preamble": []}
    current = "_preamble"
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if len(line) <= 45:
            for key, rx in _SECTION_RES.items():
                if rx.match(line):
                    current = key
                    sections.setdefault(current, [])
                    break
            else:
                sections.setdefault(current, []).append(line)
                continue
            continue
        sections.setdefault(current, []).append(line)
    return sections


def find_skills(text: str, catalogue: Catalogue, sections: dict[str, list[str]] | None = None) -> list[dict[str, Any]]:
    found: dict[int, dict[str, Any]] = {}
    sec_text = {k: "\n".join(v) for k, v in (sections or {"all": [text]}).items()}
    for sid, alias, pat in _patterns(catalogue):
        hits = pat.findall(text)
        if not hits:
            continue
        entry = found.setdefault(
            sid,
            {
                "skill_id": sid,
                "name": catalogue.skills[sid].name,
                "category": catalogue.skills[sid].category,
                "matched": set(),
                "count": 0,
                "sections": set(),
            },
        )
        entry["matched"].add(alias)
        entry["count"] += len(hits)
        for sec, body in sec_text.items():
            if pat.search(body):
                entry["sections"].add(sec)
    out = []
    for e in found.values():
        out.append({**e, "matched": sorted(e["matched"]), "sections": sorted(s for s in e["sections"] if not s.startswith("_"))})
    out.sort(key=lambda e: (-e["count"], e["name"]))
    return out


def resume_suggestions(sections: dict[str, list[str]], skills: list[dict[str, Any]], text: str) -> list[dict[str, str]]:
    tips: list[dict[str, str]] = []
    present = {k for k, v in sections.items() if v and not k.startswith("_")}
    for needed, label in (("education", "Education"), ("skills", "Skills"), ("projects", "Projects")):
        if needed not in present:
            tips.append({"code": f"missing_{needed}", "message": f"Add a clearly headed '{label}' section."})
    bullets = [line for k in ("projects", "experience") for line in sections.get(k, [])]
    weak = [b for b in bullets if b.lower().lstrip("-•* ").startswith(WEAK_STARTS)]
    if weak:
        tips.append(
            {
                "code": "weak_verbs",
                "message": (
                    f'{len(weak)} bullet(s) start with vague phrases (e.g. "{weak[0][:60]}"). Start with a specific action '
                    f"verb such as {', '.join(ACTION_VERBS[:6])}."
                ),
            }
        )
    if bullets:
        unquantified = [b for b in bullets if not re.search(r"\d", b)]
        if len(unquantified) / len(bullets) > 0.7:
            tips.append(
                {
                    "code": "quantify",
                    "message": (
                        "Most project/experience bullets contain no measurable outcome. Where you have REAL numbers "
                        "(users, latency, accuracy on a held-out set, time saved), include them. Never invent metrics."
                    ),
                }
            )
    listed_only = [s["name"] for s in skills if s["sections"] == ["skills"]]
    if listed_only:
        tips.append(
            {
                "code": "unsupported_skills",
                "message": (
                    "These skills appear only in your skills list, not in any project or experience: "
                    + ", ".join(listed_only[:8])
                    + ". Show where you used them, or remove them."
                ),
            }
        )
    if not URL_RE.search(text):
        tips.append({"code": "no_links", "message": "Consider adding links to your GitHub or portfolio, if you have them."})
    words = len(text.split())
    if words > 900:
        tips.append(
            {
                "code": "too_long",
                "message": f"At ~{words} words this is likely over one page; students "
                "usually benefit from a concise one-page resume.",
            }
        )
    return tips


def analyse_resume(text: str, catalogue: Catalogue) -> dict[str, Any]:
    sections = split_sections(text)
    skills = find_skills(text, catalogue, sections)
    project_titles = [line[:120] for line in sections.get("projects", []) if not line.lstrip().startswith(("-", "•", "*"))][:10]
    return {
        "sections": {k: len(v) for k, v in sections.items() if not k.startswith("_") and v},
        "skills": skills,
        "project_candidates": project_titles,
        "experience_lines": sections.get("experience", [])[:10],
        "suggestions": resume_suggestions(sections, skills, text),
        "word_count": len(text.split()),
        "contact_details_detected": bool(re.search(r"@|\+?\d[\d\s\-]{8,}", "\n".join(sections.get("_preamble", [])))),
        "note": "Extracted items are unverified suggestions. Confirm only what is accurate.",
    }


def analyse_job_description(text: str, catalogue: Catalogue) -> dict[str, Any]:
    skills = find_skills(text, catalogue)
    req_markers = re.compile(r"(required|must have|requirements|qualifications|you have)", re.I)
    pref_markers = re.compile(r"(nice to have|preferred|bonus|plus|good to have)", re.I)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    mode = "unspecified"
    importance: Counter[int] = Counter()
    for line in lines:
        if req_markers.search(line) and len(line) < 60:
            mode = "required"
        elif pref_markers.search(line) and len(line) < 60:
            mode = "preferred"
        for s in skills:
            if any(re.search(rf"(?<![A-Za-z0-9+#]){re.escape(a)}(?![A-Za-z0-9+#])", line, re.I) for a in s["matched"]):
                importance[s["skill_id"]] += 2 if mode == "required" else 1
    for s in skills:
        s["weight"] = importance.get(s["skill_id"], 1)
    return {
        "skills": skills,
        "word_count": len(text.split()),
        "note": "Skills are matched against the TwinPath catalogue; requirements outside it are not detected.",
    }
