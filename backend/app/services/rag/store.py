"""Vector store (Chroma, embedded) with access control applied BEFORE similarity search.

Collections
  kb_global  : authored knowledge base + admin-uploaded global documents (readable by all)
  kb_private : a student's own uploaded documents; every query is pre-filtered with
               where={"owner_id": <authenticated user id>} — the id comes from the session,
               never from the model or the client.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import chromadb

from app.config import get_settings
from app.services.rag.ollama_client import embed
from app.services.rag.text import Chunk, injection_hits, redact_pii, strip_control_tokens

log = logging.getLogger("twinpath.rag")
_lock = threading.Lock()
EMBED_BATCH = 16
DOC_PREFIX = "search_document: "  # nomic-embed-text task prefixes
QUERY_PREFIX = "search_query: "


@lru_cache
def _client() -> Any:
    path = get_settings().data_dir / "chroma"
    path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(path), settings=chromadb.Settings(anonymized_telemetry=False, allow_reset=False))


def _collection(name: str) -> Any:
    return _client().get_or_create_collection(
        name,
        embedding_function=None,
        configuration={"hnsw": {"space": "cosine"}},
        metadata={"embed_model": get_settings().ollama_embed_model},
    )


@dataclass
class IndexResult:
    chunks: int
    flagged: int


def index_chunks(
    *, doc_id: str, title: str, scope: str, owner_id: uuid.UUID | None, chunks: list[Chunk], source: str
) -> IndexResult:
    if scope == "private" and owner_id is None:
        raise ValueError("private documents require an owner")
    coll = _collection("kb_private" if scope == "private" else "kb_global")
    texts, metas, ids = [], [], []
    flagged = 0
    for ch in chunks:
        body = strip_control_tokens(redact_pii(ch.text)) if scope == "private" else strip_control_tokens(ch.text)
        # Contextual chunk header: the document title and section heading are embedded WITH the text,
        # so a chunk about "Level 3 — Proficient" is retrievable by questions about level 3 (eval run 2).
        header = f"{title} — {ch.heading}" if ch.heading else title
        clean = f"[{header}]\n{body}"
        hits = injection_hits(clean)
        flagged += bool(hits)
        texts.append(clean)
        metas.append(
            {
                "doc_id": doc_id,
                "title": title[:160],
                "heading": ch.heading[:160],
                "chunk": ch.index,
                "scope": scope,
                "owner_id": str(owner_id) if owner_id else "",
                "source": source,
                "injection_flag": bool(hits),
            }
        )
        ids.append(f"{doc_id}:{ch.index}")
    with _lock:
        delete_document(doc_id, scope)
        for i in range(0, len(texts), EMBED_BATCH):
            vectors = embed([DOC_PREFIX + t for t in texts[i : i + EMBED_BATCH]])
            coll.add(
                ids=ids[i : i + EMBED_BATCH],
                embeddings=vectors,
                documents=texts[i : i + EMBED_BATCH],
                metadatas=metas[i : i + EMBED_BATCH],
            )
    return IndexResult(chunks=len(texts), flagged=flagged)


def delete_document(doc_id: str, scope: str) -> None:
    coll = _collection("kb_private" if scope == "private" else "kb_global")
    coll.delete(where={"doc_id": doc_id})


def delete_owner(owner_id: uuid.UUID) -> None:
    _collection("kb_private").delete(where={"owner_id": str(owner_id)})


@dataclass
class Passage:
    ref: str
    doc_id: str
    title: str
    heading: str
    scope: str
    text: str
    distance: float
    source: str


def retrieve(query: str, *, user_id: uuid.UUID, k: int = 5, max_distance: float = 0.65) -> list[Passage]:
    """Top-k passages from the global KB and the caller's OWN private documents.
    Passages flagged as possible prompt injection are excluded from model context."""
    qvec = embed([QUERY_PREFIX + query[:1500]])[0]
    found: list[Passage] = []
    for name, where in (
        ("kb_global", {"injection_flag": False}),
        ("kb_private", {"$and": [{"owner_id": str(user_id)}, {"injection_flag": False}]}),
    ):
        coll = _collection(name)
        if coll.count() == 0:
            continue
        res = coll.query(
            query_embeddings=[qvec], n_results=min(k, coll.count()), where=where, include=["documents", "metadatas", "distances"]
        )
        for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0], strict=True):
            if name == "kb_private" and meta.get("owner_id") != str(user_id):  # belt and braces
                continue
            if dist <= max_distance:
                found.append(
                    Passage(
                        "",
                        meta["doc_id"],
                        meta["title"],
                        meta.get("heading", ""),
                        meta["scope"],
                        doc,
                        float(dist),
                        meta.get("source", ""),
                    )
                )
    found.sort(key=lambda p: p.distance)
    seen: set[tuple[str, str]] = set()
    unique = []
    for p in found:
        key = (p.doc_id, p.text[:80])
        if key not in seen:
            seen.add(key)
            unique.append(p)
    for i, p in enumerate(unique[:k], start=1):
        p.ref = f"S{i}"
    return unique[:k]


def stats() -> dict[str, int]:
    try:
        return {"global_chunks": _collection("kb_global").count(), "private_chunks": _collection("kb_private").count()}
    except Exception:  # pragma: no cover - diagnostics only
        return {"global_chunks": -1, "private_chunks": -1}
