"""Mentor chat endpoints with Server-Sent-Events streaming from the LOCAL Ollama model."""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import StreamingResponse
from pydantic import Field
from sqlalchemy import func, select
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.db import get_session_factory, set_rls_subject
from app.deps import DB, CurrentUser
from app.errors import AppError, NotFound, ServiceUnavailable
from app.models import MentorConversation, MentorMessage
from app.schemas.common import Message, StrictModel
from app.security.ratelimit import MENTOR_USER, limiter
from app.services.rag import mentor as svc
from app.services.rag.ollama_client import OllamaUnavailable, chat_stream, ollama_status_cached

router = APIRouter(prefix="/mentor", tags=["mentor"])
log = logging.getLogger("twinpath.mentor")
UNAVAILABLE_TEXT = (
    "The local AI mentor is currently unavailable (the Ollama service or the configured model is "
    "not running). No answer was generated. Your other TwinPath features keep working."
)


class AskIn(StrictModel):
    question: str = Field(min_length=2, max_length=8000)
    conversation_id: uuid.UUID | None = None


@router.get("/status")
def mentor_status(_principal: CurrentUser) -> dict[str, Any]:
    st = ollama_status_cached()
    return {
        "available": bool(st.get("reachable") and st.get("chat_model_available") and st.get("embed_model_available")),
        "chat_model": get_settings().ollama_chat_model,
        "embed_model": get_settings().ollama_embed_model,
        "runtime": "Ollama (local)",
        "queue": svc.gate().stats(),
    }


@router.get("/conversations")
def list_conversations(principal: CurrentUser, db: DB) -> dict[str, Any]:
    rows = db.scalars(
        select(MentorConversation)
        .where(MentorConversation.user_id == principal.id)
        .order_by(MentorConversation.updated_at.desc())
        .limit(100)
    ).all()
    return {"items": [{"id": c.id, "title": c.title, "updated_at": c.updated_at} for c in rows]}


def _owned_conversation(db: DB, user_id: uuid.UUID, conversation_id: uuid.UUID) -> MentorConversation:
    conv = db.scalar(
        select(MentorConversation).where(MentorConversation.id == conversation_id, MentorConversation.user_id == user_id)
    )
    if conv is None:
        raise NotFound("Conversation not found.")
    return conv


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: uuid.UUID, principal: CurrentUser, db: DB) -> dict[str, Any]:
    conv = _owned_conversation(db, principal.id, conversation_id)
    msgs = db.scalars(
        select(MentorMessage).where(MentorMessage.conversation_id == conv.id).order_by(MentorMessage.created_at)
    ).all()
    return {
        "id": conv.id,
        "title": conv.title,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "sources": m.sources,
                "status": m.status,
                "context_sections": m.context_sections,
                "model_tag": m.model_tag,
                "latency_ms": m.latency_ms,
                "created_at": m.created_at,
            }
            for m in msgs
        ],
    }


@router.delete("/conversations/{conversation_id}", response_model=Message)
def delete_conversation(conversation_id: uuid.UUID, principal: CurrentUser, db: DB) -> Message:
    db.delete(_owned_conversation(db, principal.id, conversation_id))
    db.commit()
    return Message(message="Conversation deleted.")


def _sse(event: str, data: dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n".encode()


def _save_assistant(
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    content: str,
    *,
    status_: str,
    sources: list[dict[str, Any]],
    sections: list[str],
    latency_ms: int | None,
    prompt_tokens: int | None,
    completion_tokens: int | None,
) -> uuid.UUID:
    db = get_session_factory()()
    try:
        set_rls_subject(db, user_id)
        msg = MentorMessage(
            conversation_id=conversation_id,
            user_id=user_id,
            role="assistant",
            content=content or "",
            status=status_,
            sources=sources,
            context_sections=sections,
            model_tag=get_settings().ollama_chat_model,
            latency_ms=latency_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        db.add(msg)
        conv = db.get(MentorConversation, conversation_id)
        if conv is not None:
            conv.updated_at = func.now()
        db.commit()
        return msg.id
    finally:
        db.close()


def _sanitize(text: str) -> tuple[str, int]:
    from app.services.catalogue import load_catalogue

    db = get_session_factory()()
    try:
        allowed = {r.url for r in load_catalogue(db).resources.values()}
    finally:
        db.close()
    return svc.sanitize_links(text, allowed)


@router.post("/ask")
async def ask(body: AskIn, request: Request, principal: CurrentUser, db: DB) -> StreamingResponse:
    settings = get_settings()
    if len(body.question) > settings.mentor_max_question_chars:
        raise AppError(
            f"Questions are limited to {settings.mentor_max_question_chars} characters.",
            code="question_too_long",
            status_code=422,
        )
    limiter.hit(MENTOR_USER, str(principal.id))
    user_id = principal.id

    st = await run_in_threadpool(ollama_status_cached)
    if not (st.get("reachable") and st.get("chat_model_available") and st.get("embed_model_available")):
        raise ServiceUnavailable(UNAVAILABLE_TEXT, code="mentor_unavailable")

    def prepare() -> tuple[uuid.UUID, svc.MentorContext, list[dict[str, str]]]:
        if body.conversation_id:
            conv = _owned_conversation(db, user_id, body.conversation_id)
        else:
            conv = MentorConversation(user_id=user_id, title=body.question[:80])
            db.add(conv)
            db.flush()
        history = db.scalars(
            select(MentorMessage)
            .where(MentorMessage.conversation_id == conv.id, MentorMessage.status == "complete")
            .order_by(MentorMessage.created_at.desc())
            .limit(8)
        ).all()
        db.add(MentorMessage(conversation_id=conv.id, user_id=user_id, role="user", content=body.question))
        ctx = svc.assemble(db, user_id, body.question, list(reversed(history)))
        db.commit()
        return conv.id, ctx, svc.build_messages(ctx, body.question)

    try:
        conversation_id, ctx, messages = await run_in_threadpool(prepare)
    except OllamaUnavailable as exc:
        raise ServiceUnavailable(UNAVAILABLE_TEXT, code="mentor_unavailable") from exc

    sources = svc.sources_payload(ctx.passages)

    async def stream() -> AsyncIterator[bytes]:
        started = svc.now_ms()
        answer: list[str] = []
        status_ = "error"
        stats: dict[str, Any] = {}
        yield _sse(
            "meta",
            {
                "conversation_id": str(conversation_id),
                "sources": sources,
                "context_sections": ctx.sections,
                "model": settings.ollama_chat_model,
                "prompt_tokens_estimate": svc.prompt_tokens_estimate(messages),
            },
        )
        try:
            async with svc.gate():
                yield _sse("status", {"state": "generating"})
                async for chunk in chat_stream(messages, num_predict=svc.ANSWER_TOKENS):
                    if await request.is_disconnected():
                        status_ = "cancelled"
                        break
                    if "delta" in chunk:
                        answer.append(chunk["delta"])
                        yield _sse("delta", {"text": chunk["delta"]})
                    elif chunk.get("done"):
                        stats = chunk
                        status_ = "complete"
            # Links the model wrote that are not verified catalogue URLs are removed before the
            # answer is stored; the client replaces its streamed text with this final version.
            text, removed_links = await run_in_threadpool(_sanitize, "".join(answer).strip())
            flagged = svc.unverified_numbers(text, ctx) if status_ == "complete" else []
            latency = int(svc.now_ms() - started)
            svc.gate().completed += 1
            svc.gate().last_latency_ms = latency
            msg_id = await run_in_threadpool(
                _save_assistant,
                user_id,
                conversation_id,
                text,
                status_=status_,
                sources=sources,
                sections=ctx.sections,
                latency_ms=latency,
                prompt_tokens=stats.get("prompt_tokens"),
                completion_tokens=stats.get("completion_tokens"),
            )
            yield _sse(
                "done",
                {
                    "message_id": str(msg_id),
                    "status": status_,
                    "latency_ms": latency,
                    "prompt_tokens": stats.get("prompt_tokens"),
                    "completion_tokens": stats.get("completion_tokens"),
                    "truncated": stats.get("done_reason") == "length",
                    "unverified_numbers": flagged,
                    "removed_links": removed_links,
                    "content": text,
                },
            )
        except svc.MentorBusy:
            yield _sse(
                "error",
                {"code": "mentor_busy", "message": "The local mentor is busy with other requests. Please try again shortly."},
            )
        except OllamaUnavailable:
            svc.gate().failed += 1
            await run_in_threadpool(
                _save_assistant,
                user_id,
                conversation_id,
                "".join(answer),
                status_="unavailable",
                sources=sources,
                sections=ctx.sections,
                latency_ms=None,
                prompt_tokens=None,
                completion_tokens=None,
            )
            yield _sse("error", {"code": "mentor_unavailable", "message": UNAVAILABLE_TEXT})
        except TimeoutError:
            svc.gate().failed += 1
            yield _sse("error", {"code": "mentor_timeout", "message": "The local model took too long to respond."})

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        status_code=status.HTTP_200_OK,
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
