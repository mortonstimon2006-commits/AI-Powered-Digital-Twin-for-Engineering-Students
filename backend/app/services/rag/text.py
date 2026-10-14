"""Chunking, PII redaction and prompt-injection screening for retrieved text."""

from __future__ import annotations

import re
from dataclasses import dataclass

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\s\-().]{0,2}){9,14}\d(?!\d)")
CONTROL_TOKENS = re.compile(r"<\|[^|>]{1,40}\|>|</?think>|</?(system|assistant|user)>", re.IGNORECASE)

INJECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore (all |any |the )?(previous|prior|above|earlier) (instructions|prompts|messages|rules)",
        r"disregard (all |any |the )?(previous|prior|above|system) (instructions|prompt|rules)",
        r"forget (everything|all|your) (instructions|rules|previous)",
        r"you are now (a|an|the|in) ",
        r"(reveal|print|show|repeat|output) (me )?(your|the) (system prompt|instructions|hidden prompt|rules)",
        r"(developer|dan|jailbreak|god) mode",
        r"new instructions?:",
        r"\bsystem prompt\b",
        r"override (the |your )?(safety|rules|instructions)",
        r"(send|post|upload|exfiltrate) .{0,40}(data|profile|password|token|key)s? to",
        r"\bact as (an? )?(admin|administrator|system|root)\b",
    )
]


def redact_pii(text: str) -> str:
    text = EMAIL_RE.sub("[email]", text)
    return PHONE_RE.sub("[phone]", text)


def strip_control_tokens(text: str) -> str:
    return CONTROL_TOKENS.sub(" ", text)


def injection_hits(text: str) -> list[str]:
    return [p.pattern for p in INJECTION_PATTERNS if p.search(text)]


@dataclass
class Chunk:
    index: int
    heading: str
    text: str


def chunk_text(text: str, *, target_chars: int = 900, overlap_chars: int = 150) -> list[Chunk]:
    """Heading-aware chunking: split on markdown headings, then pack paragraphs up to
    ~target_chars with a small overlap so context is not cut mid-thought."""
    text = text.replace("\r\n", "\n")
    sections: list[tuple[str, str]] = []
    heading: str = ""
    buf: list[str] = []
    for line in text.split("\n"):
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            if "".join(buf).strip():
                sections.append((heading, "\n".join(buf).strip()))
            heading, buf = m.group(2).strip(), []
        else:
            buf.append(line)
    if "".join(buf).strip():
        sections.append((heading, "\n".join(buf).strip()))

    chunks: list[Chunk] = []
    for head, body in sections:
        paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
        current = ""
        for p in paras:
            while len(p) > target_chars * 1.5:  # hard-split very long paragraphs
                cut = p.rfind(" ", 0, target_chars)
                cut = cut if cut > target_chars // 2 else target_chars
                if current:
                    chunks.append(Chunk(len(chunks), head, current))
                    current = ""
                chunks.append(Chunk(len(chunks), head, p[:cut].strip()))
                p = p[max(cut - overlap_chars, 0) :].strip()
            if current and len(current) + len(p) + 2 > target_chars:
                chunks.append(Chunk(len(chunks), head, current))
                tail = current[-overlap_chars:]
                current = (tail[tail.find(" ") + 1 :] if " " in tail else tail) + "\n\n" + p
            else:
                current = f"{current}\n\n{p}" if current else p
        if current:
            chunks.append(Chunk(len(chunks), head, current))
    return chunks
