"""Chat message — create a message in an attempt chat.

POST /attempt/chat/message

Pure data primitive. Creates attempt_message_entry + attempt_content_entry.
Runs through the audit layer so ``attempt.chat_message.started`` /
``attempt.chat_message.completed`` fire for the client's optimistic UI —
same event shape as the AI-driven tool-call path.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

from app.infra.attempt.message import (
    AttemptMessageInternalResult,
    attempt_message_internal_impl,
)
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client
from app.infra.group.resolve import resolve_group_impl
from app.infra.websocket.get_socket_owner import get_socket_owner

router = APIRouter()


class ChatMessageRequest(BaseModel):
    chat_id: UUID
    text: str
    persona_id: UUID | None = None
    parent_message_id: UUID | None = None
    # When True (default), the server auto-links the new message to
    # the chat's latest prior message if `parent_message_id` is None.
    # Fork callers pass False to force an explicit root (parent stays
    # null) when the fork target has no parent of its own.
    auto_link_parent: bool = True


class ChatMessageResponse(BaseModel):
    success: bool
    message_id: str
    content_ids: list[str]


@router.post("/chat_message", response_model=ChatMessageResponse)
async def chat_message(
    request: ChatMessageRequest,
    http_request: Request,
) -> ChatMessageResponse:
    """Create a message in an attempt chat."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    logger.info(
        f"VOICE_TRACE[4] /attempt/chat/message: chat_id={request.chat_id} "
        f"text={request.text[:60]!r} persona_id={request.persona_id} "
        f"profile_id={profile_id}"
    )
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    # Resolve the caller's socket id so audit events route back to the
    # right client. HTTP doesn't carry a socket id directly, so look it
    # up by profile from the owner index maintained by the WS layer.
    sid = getattr(http_request.state, "sid", None)
    if not sid:
        sid = await get_socket_owner(str(profile_id)) or ""

    pool = get_pool()
    redis = get_redis_client()

    # Resolve the current attempt group so audit can record the call.
    # Without a group_id the audit layer falls to its non-audit branch
    # and emits an empty .completed event — defeats the client swap.
    group_resolve = await resolve_group_impl(
        pool,
        redis,
        artifact_type="attempt",
        profile_id=profile_id,
        session_id=session_id,
        include_history=False,
    )
    group_id = group_resolve.group_id

    async def _runner() -> AttemptMessageInternalResult:
        return await attempt_message_internal_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            chat_id=request.chat_id,
            text=request.text,
            persona_id=request.persona_id,
            parent_message_id=request.parent_message_id,
            auto_link_parent=request.auto_link_parent,
        )

    try:
        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="attempt",
            operation="chat_message",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            sid=sid,
            runner=_runner,
            arguments={
                "chat_id": str(request.chat_id),
                "text": request.text,
                "persona_id": str(request.persona_id) if request.persona_id else None,
            },
            response_model=AttemptMessageInternalResult,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ChatMessageResponse(
        success=result.success,
        message_id=result.message_id or "",
        content_ids=result.content_ids,
    )
