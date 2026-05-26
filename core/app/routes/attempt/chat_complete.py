"""Chat complete — mark an attempt chat as completed.

POST /attempt/chat/complete — canonical: idempotency replay + soft/accept
(stage-inactive) through the audit wrapper.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.attempt.chat_complete import chat_complete_attempt_impl
from app.infra.attempt.group import group_attempt_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder

router = APIRouter()


class ChatCompleteRequest(BaseModel):
    chat_id: UUID
    message: str = ""
    idempotency_key: UUID | None = None
    soft: bool = False
    accept: bool | None = None


class ChatCompleteResponse(BaseModel):
    success: bool
    completion_id: str
    chat_id: str
    idempotency_key: str | None = None


@router.post("/chat_complete", response_model=ChatCompleteResponse)
async def chat_complete(
    request: ChatCompleteRequest,
    http_request: Request,
) -> ChatCompleteResponse:
    """Mark an attempt chat as completed — final step after grading."""
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

    async def _runner(call_id: UUID | None = None) -> ChatCompleteResponse:
        result = await chat_complete_attempt_impl(
            pool, redis,
            profile_id=profile_id, session_id=session_id,
            chat_id=request.chat_id, message=request.message,
            soft=request.soft, accept=request.accept,
            idempotency_key=request.idempotency_key, call_id=call_id,
        )
        return ChatCompleteResponse(
            success=True,
            completion_id=result["completion_id"],
            chat_id=result["chat_id"],
            idempotency_key=result.get("idempotency_key"),
        )

    try:
        return await run_artifact_operation_with_audit(
            pool, redis,
            artifact="attempt",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_result.group_id,
            operation="chat_complete",
            arguments={"accept": request.accept} if is_ack else request.model_dump(mode="json"),
            operation_key=request.idempotency_key,
            response_model=ChatCompleteResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
