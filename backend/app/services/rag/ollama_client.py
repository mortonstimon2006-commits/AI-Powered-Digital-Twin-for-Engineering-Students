"""Minimal client for the LOCAL Ollama runtime.

There is deliberately no fallback: if the configured chat or embedding model is missing,
the mentor reports itself unavailable. No external LLM API is used anywhere.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import get_settings

log = logging.getLogger("twinpath.ollama")

_STATUS_TTL = 15.0
_status_cache: dict[str, Any] = {"at": 0.0, "value": {"reachable": False}}
_status_lock = threading.Lock()


class OllamaUnavailable(Exception):
    pass


def _model_present(name: str, tags: list[str]) -> bool:
    # Ollama reports untagged pulls as "<name>:latest".
    wanted = name if ":" in name else f"{name}:latest"
    return wanted in tags


def fetch_status(timeout: float = 2.0) -> dict[str, Any]:
    s = get_settings()
    try:
        with httpx.Client(base_url=s.ollama_base_url, timeout=timeout) as client:
            tags_resp = client.get("/api/tags")
            tags_resp.raise_for_status()
            models = tags_resp.json().get("models", [])
            names = [m.get("name", "") for m in models]
            details = {m.get("name"): m.get("details", {}) for m in models}
            ps = client.get("/api/ps").json().get("models", [])
            version = client.get("/api/version").json().get("version")
        chat_ok = _model_present(s.ollama_chat_model, names)
        return {
            "reachable": True,
            "ollama_version": version,
            "chat_model": s.ollama_chat_model,
            "chat_model_available": chat_ok,
            "chat_model_quantization": details.get(s.ollama_chat_model, {}).get("quantization_level"),
            "embed_model": s.ollama_embed_model,
            "embed_model_available": _model_present(s.ollama_embed_model, names),
            "num_ctx": s.ollama_num_ctx,
            "loaded": [
                {
                    "name": m.get("name"),
                    "size_vram_mb": round((m.get("size_vram") or 0) / 2**20),
                    "context_length": m.get("context_length"),
                }
                for m in ps
            ],
        }
    except Exception as exc:
        return {"reachable": False, "chat_model_available": False, "embed_model_available": False, "error": type(exc).__name__}


def ollama_status_cached() -> dict[str, Any]:
    with _status_lock:
        if time.monotonic() - _status_cache["at"] > _STATUS_TTL:
            _status_cache["value"] = fetch_status()
            _status_cache["at"] = time.monotonic()
        return dict(_status_cache["value"])


def invalidate_status() -> None:
    with _status_lock:
        _status_cache["at"] = 0.0


def embed(texts: list[str], *, timeout: float = 60.0) -> list[list[float]]:
    """Embeds texts with the local embedding model. Callers add nomic task prefixes."""
    s = get_settings()
    if not texts:
        return []
    try:
        with httpx.Client(base_url=s.ollama_base_url, timeout=timeout) as client:
            resp = client.post("/api/embed", json={"model": s.ollama_embed_model, "input": texts, "truncate": True})
            if resp.status_code == 404:
                raise OllamaUnavailable(f"embedding model '{s.ollama_embed_model}' is not installed")
            resp.raise_for_status()
            vectors = resp.json().get("embeddings")
    except httpx.HTTPError as exc:
        raise OllamaUnavailable(f"Ollama unreachable: {type(exc).__name__}") from exc
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        raise OllamaUnavailable("unexpected embedding response")
    return vectors


async def chat_stream(
    messages: list[dict[str, str]], *, temperature: float = 0.3, num_predict: int = 700
) -> AsyncIterator[dict[str, Any]]:
    """Streams chat chunks from the local model. Yields {'delta': str} and finally
    {'done': True, 'prompt_tokens', 'completion_tokens', 'total_ms'}."""
    s = get_settings()
    payload = {
        "model": s.ollama_chat_model,
        "messages": messages,
        "stream": True,
        "think": False,  # Qwen3 hybrid reasoning off: lower latency on 8 GB consumer GPUs
        "keep_alive": "10m",
        "options": {"num_ctx": s.ollama_num_ctx, "temperature": temperature, "num_predict": num_predict},
    }
    timeout = httpx.Timeout(s.ollama_timeout_seconds, connect=5.0)
    try:
        async with (
            httpx.AsyncClient(base_url=s.ollama_base_url, timeout=timeout) as client,
            client.stream("POST", "/api/chat", json=payload) as resp,
        ):
            if resp.status_code == 404:
                raise OllamaUnavailable(f"chat model '{s.ollama_chat_model}' is not installed")
            if resp.status_code >= 400:
                raise OllamaUnavailable(f"Ollama returned HTTP {resp.status_code}")
            async for line in resp.aiter_lines():
                if not line.strip():
                    continue
                chunk = json.loads(line)
                if chunk.get("error"):
                    raise OllamaUnavailable("model error during generation")
                content = (chunk.get("message") or {}).get("content", "")
                if content:
                    yield {"delta": content}
                if chunk.get("done"):
                    yield {
                        "done": True,
                        "prompt_tokens": chunk.get("prompt_eval_count"),
                        "completion_tokens": chunk.get("eval_count"),
                        "total_ms": round((chunk.get("total_duration") or 0) / 1e6),
                        "eval_ms": round((chunk.get("eval_duration") or 0) / 1e6),
                        "done_reason": chunk.get("done_reason"),
                    }
    except httpx.HTTPError as exc:
        raise OllamaUnavailable(f"Ollama unreachable: {type(exc).__name__}") from exc
