"""Local-inference benchmark: cold/warm latency, prompt-processing and generation speed,
GPU memory (from Ollama /api/ps and, when available, nvidia-smi) at the configured num_ctx."""

from __future__ import annotations

import asyncio
import shutil
import statistics
import subprocess
import time
from typing import Any

import httpx

from app.config import get_settings
from app.services.rag.mentor import SYSTEM_PROMPT

BENCH_CONTEXT = "\n".join(
    [f"- Skill {i}: level {i % 4 + 1}/4 (self reported)" for i in range(40)]
    + ["Student question: Which two skills should I prioritise this month for a data analyst role, and why?"]
)


def _nvidia_smi() -> dict[str, Any] | None:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return None
    try:
        # Fixed executable resolved by shutil.which and constant arguments — no user input.
        proc = subprocess.run(  # noqa: S603
            [exe, "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        out = proc.stdout.strip().splitlines()[0]
        name, total, used = [x.strip() for x in out.split(",")]
        return {"gpu": name, "memory_total_mb": int(total), "memory_used_mb": int(used)}
    except Exception:
        return None


def _one(client: httpx.Client, num_ctx: int, keep_alive: str) -> dict[str, Any]:
    s = get_settings()
    t0 = time.perf_counter()
    nonce = f"[benchmark run {time.time_ns()}]\n"  # unique prefix defeats Ollama's prompt cache
    r = client.post(
        "/api/chat",
        json={
            "model": s.ollama_chat_model,
            "stream": False,
            "think": False,
            "keep_alive": keep_alive,
            "messages": [{"role": "system", "content": nonce + SYSTEM_PROMPT}, {"role": "user", "content": BENCH_CONTEXT}],
            "options": {"num_ctx": num_ctx, "temperature": 0.3, "num_predict": 200, "seed": 1},
        },
    )
    r.raise_for_status()
    d = r.json()
    wall = time.perf_counter() - t0
    ns = 1e9
    return {
        "wall_s": round(wall, 2),
        "load_s": round(d.get("load_duration", 0) / ns, 2),
        "prompt_tokens": d.get("prompt_eval_count"),
        "prompt_tok_per_s": round(d["prompt_eval_count"] / (d["prompt_eval_duration"] / ns), 1)
        if d.get("prompt_eval_duration")
        else None,
        "gen_tokens": d.get("eval_count"),
        "gen_tok_per_s": round(d["eval_count"] / (d["eval_duration"] / ns), 1) if d.get("eval_duration") else None,
    }


def run_benchmark(runs: int = 3) -> dict[str, Any]:
    s = get_settings()
    out: dict[str, Any] = {"model": s.ollama_chat_model, "num_ctx": s.ollama_num_ctx, "gpu_before": _nvidia_smi()}
    with httpx.Client(base_url=s.ollama_base_url, timeout=600) as client:
        client.post("/api/generate", json={"model": s.ollama_chat_model, "keep_alive": 0})  # unload -> cold start
        time.sleep(2)
        out["cold"] = _one(client, s.ollama_num_ctx, "10m")
        warm = [_one(client, s.ollama_num_ctx, "10m") for _ in range(runs)]
        out["warm_runs"] = warm
        out["warm_median"] = {
            k: statistics.median([w[k] for w in warm if w[k] is not None])
            for k in ("wall_s", "prompt_tok_per_s", "gen_tok_per_s")
        }
        ps = client.get("/api/ps").json().get("models", [])
        out["loaded"] = [
            {
                "name": m.get("name"),
                "size_mb": round(m.get("size", 0) / 2**20),
                "size_vram_mb": round(m.get("size_vram", 0) / 2**20),
                "gpu_offload_share": round(m.get("size_vram", 0) / m["size"], 3) if m.get("size") else None,
                "context_length": m.get("context_length"),
            }
            for m in ps
        ]

        # concurrency probe: two simultaneous requests should be serialised by the API gate;
        # here we measure what Ollama itself does when hit concurrently (documented, not hidden).
        async def both() -> list[float]:
            async with httpx.AsyncClient(base_url=s.ollama_base_url, timeout=600) as ac:

                async def call() -> float:
                    t = time.perf_counter()
                    await ac.post(
                        "/api/chat",
                        json={
                            "model": s.ollama_chat_model,
                            "stream": False,
                            "think": False,
                            "messages": [{"role": "user", "content": "Say OK."}],
                            "options": {"num_ctx": s.ollama_num_ctx, "num_predict": 8},
                        },
                    )
                    return round(time.perf_counter() - t, 2)

                return list(await asyncio.gather(call(), call()))

        out["two_concurrent_requests_wall_s"] = asyncio.run(both())
    out["gpu_after"] = _nvidia_smi()
    return out
