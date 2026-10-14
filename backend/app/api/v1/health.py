from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db import get_engine

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready() -> JSONResponse:
    """Readiness for load balancers. Reports component status only (no versions, hosts or
    errors). The mentor/LLM is optional: its absence degrades, but does not fail, readiness."""
    from app.ml.registry import registry
    from app.services.rag.ollama_client import ollama_status_cached

    checks: dict[str, str] = {}
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"
    checks["readiness_model"] = "ok" if registry.active_available() else "unavailable"
    checks["mentor_llm"] = "ok" if ollama_status_cached().get("chat_model_available") else "unavailable"
    healthy = checks["database"] == "ok"
    overall = "ok" if all(v == "ok" for v in checks.values()) else ("degraded" if healthy else "down")
    return JSONResponse(status_code=200 if healthy else 503, content={"status": overall, "checks": checks})
