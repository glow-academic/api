"""Chat audio — attach audio to a chat message.

POST /attempt/chat/audio — canonical: idempotency replay + soft/accept
(stage-inactive) through the audit wrapper. Creates an ``attempt_audio_entry``
row linking a message to a resource-level ``audios_id``.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.attempt.chat_audio import attempt_chat_audio_internal_impl
from app.infra.attempt.group import group_attempt_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder

router = APIRouter()


class ChatAudioRequest(BaseModel):
    chat_id: UUID
    message_id: UUID | None = None
    audios_id: UUID | None = None
    idempotency_key: UUID | None = None
    soft: bool = False
    accept: bool | None = None


class ChatAudioResponse(BaseModel):
    success: bool
    attempt_audio_id: str
    idempotency_key: str | None = None


@router.post("/chat_audio", response_model=ChatAudioResponse)
async def chat_audio(
    request: ChatAudioRequest,
    http_request: Request,
) -> ChatAudioResponse:
    """Attach an audios_id to an attempt chat message."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")
    profile_id = UUID(str(profile_id))
    session_id = UUID(str(session_id))
    pool = get_pool()
    redis = get_redis_client()

    group_result = await group_attempt_impl(
        pool, redis, profile_id=profile_id, session_id=session_id, id_only=True,
    )
    is_ack = request.accept is not None and request.idempotency_key is not None

    async def _runner(call_id: UUID | None = None) -> ChatAudioResponse:
        result = await attempt_chat_audio_internal_impl(
            pool, redis,
            profile_id=profile_id, session_id=session_id,
            message_id=request.message_id, audios_id=request.audios_id,
            soft=request.soft, accept=request.accept,
            idempotency_key=request.idempotency_key, call_id=call_id,
        )
        return ChatAudioResponse(
            success=result.success, attempt_audio_id=result.attempt_audio_id,
            idempotency_key=result.idempotency_key,
        )

    try:
        return await run_artifact_operation_with_audit(
            pool, redis,
            artifact="attempt",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_result.group_id,
            operation="chat_audio",
            arguments={"accept": request.accept} if is_ack else request.model_dump(mode="json"),
            operation_key=request.idempotency_key,
            response_model=ChatAudioResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
