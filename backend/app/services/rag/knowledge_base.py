"""Indexes the authored knowledge base (repo /knowledge/*.md) and role guides generated from
the live catalogue, so mentor answers about roles always match the current framework."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import REPO_DIR
from app.models import Document
from app.services.catalogue import load_catalogue
from app.services.rag.store import index_chunks
from app.services.rag.text import chunk_text

KNOWLEDGE_DIR = REPO_DIR / "knowledge"
LEVEL_NAMES = {1: "Awareness", 2: "Working", 3: "Proficient", 4: "Advanced"}


def _title(text: str, fallback: str) -> tuple[str, str]:
    m = re.match(r"^---\s*\ntitle:\s*(.+?)\n---\s*\n", text)
    if m:
        return m.group(1).strip(), text[m.end() :]
    return fallback, text


def role_guides(db: Session) -> list[tuple[str, str, str]]:
    cat = load_catalogue(db)
    out = []
    for role in cat.roles.values():
        lines = [
            f"# {role.name} — TwinPath role requirements (version {role.version})",
            "",
            role.description,
            "",
            f"Source of this specification: {role.source_note}",
            "",
            "## Core requirements",
            "",
        ]
        groups: dict[str, list[str]] = {}
        for q in role.requirements:
            s = cat.skills[q.skill_id]
            line = (
                f"- {s.name}: level {q.required_level} ({LEVEL_NAMES[q.required_level]}), importance "
                f"{q.importance:g}, evidence expected: {q.evidence_expected}. Why: {q.rationale}"
            )
            if q.alt_group:
                groups.setdefault(q.alt_group, []).append(s.name)
            if q.is_core:
                lines.append(line)
        lines += ["", "## Optional (valued but not required)", ""]
        lines += [
            f"- {cat.skills[q.skill_id].name}: level {q.required_level}. Why: {q.rationale}"
            for q in role.requirements
            if not q.is_core
        ]
        if groups:
            lines += ["", "## Alternatives", ""]
            lines += [f"- Any one of: {', '.join(v)} satisfies the '{k}' requirement." for k, v in groups.items()]
        prereq_lines = []
        for q in role.requirements:
            for pid, lvl in cat.prerequisites.get(q.skill_id, []):
                prereq_lines.append(f"- {cat.skills[q.skill_id].name} builds on {cat.skills[pid].name} (level {lvl}+).")
        if prereq_lines:
            lines += ["", "## Prerequisite relationships", "", *sorted(set(prereq_lines))]
        out.append((f"role-guide:{role.slug}", f"{role.name} role guide", "\n".join(lines)))
    return out


def reindex_global(db: Session) -> dict[str, Any]:
    docs: list[tuple[str, str, str, str]] = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        title, body = _title(raw, path.stem.replace("-", " ").title())
        docs.append((f"kb:{path.stem}", title, body, f"knowledge/{path.name}"))
    for key, title, body in role_guides(db):
        docs.append((key, title, body, "generated from role catalogue"))

    report = []
    for key, title, body, source in docs:
        doc = db.scalar(select(Document).where(Document.scope == "global", Document.original_filename == key))
        digest = hashlib.sha256(body.encode()).hexdigest()
        if doc is None:
            doc = Document(
                owner_id=None,
                scope="global",
                kind="knowledge",
                title=title,
                original_filename=key,
                mime_type="text/markdown",
                size_bytes=len(body.encode()),
                sha256=digest,
                status="uploaded",
            )
            db.add(doc)
            db.flush()
        chunks = chunk_text(body)
        result = index_chunks(doc_id=str(doc.id), title=title, scope="global", owner_id=None, chunks=chunks, source=source)
        doc.title, doc.sha256, doc.size_bytes = title, digest, len(body.encode())
        doc.status, doc.chunk_count, doc.injection_flags, doc.error = "indexed", result.chunks, result.flagged, None
        report.append({"title": title, "chunks": result.chunks, "flagged": result.flagged})
    db.flush()
    return {"documents": len(report), "chunks": sum(r["chunks"] for r in report), "items": report}


def knowledge_files() -> list[Path]:
    return sorted(KNOWLEDGE_DIR.glob("*.md"))
