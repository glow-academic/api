"""Attempt complete — mark an entire attempt as completed.

POST /attempt/complete — routed through the audit wrapper (idempotency + soft/accept).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.infra.attempt.complete import complete_attempt_impl
from app.infra.attempt.group import group_attempt_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder

router = APIRouter()


class AttemptCompleteRequest(BaseModel):
    attempt_id: UUID | None = Field(None, description="Attempt to complete (omit on the ack call)")
    message: str = ""
    idempotency_key: UUID | None = Field(
        None,
        description="Idempotency key — replays the prior call; on the ack, the "
        "server-minted soft key to activate/reject a staged completion",
    )
    soft: bool = Field(
        False,
        description="Stage the completion dormant (active=False) — agent proposes; "
        "accept activates it. Composes into a dormant benchmark scenario.",
    )
    accept: bool | None = Field(
        None,
        description="Ack: True activates the staged completion, False rejects. Only "
        "meaningful with idempotency_key",
    )


class AttemptCompleteResponse(BaseModel):
    success: bool
    completion_id: str
    attempt_id: str
    idempotency_key: UUID | None = Field(
        None,
        description="Server-minted soft-call key (audit call_id). On a soft propose, "
        "echo this back with accept to activate/reject the staged completion.",
    )


@router.post("/complete", response_model=AttemptCompleteResponse)
async def attempt_complete(
    request: AttemptCompleteRequest,
    http_request: Request,
) -> AttemptCompleteResponse:
    """Mark an entire attempt as completed."""
    profile_id_str = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id_str or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")
    profile_id = UUID(profile_id_str)
    pool = get_pool()
    redis = get_redis_client()

    # Resolve time-windowed group for audit linking
    group_id = None
    if session_id:
        group_result = await group_attempt_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            id_only=True,
        )
        group_id = group_result.group_id

    is_ack = request.accept is not None and request.idempotency_key is not None

    async def _runner(call_id: UUID | None = None) -> AttemptCompleteResponse:
        return await complete_attempt_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            attempt_id=request.attempt_id,
            message=request.message,
            soft=request.soft,
            accept=request.accept,
            idempotency_key=request.idempotency_key,
            call_id=call_id,
        )

    return await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="attempt",
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        attempt_id=request.attempt_id,
        operation="complete",
        # On ack, carry only `accept` so the gate's _is_bare_ack skips it.
        arguments={"accept": request.accept} if is_ack else request.model_dump(mode="json"),
        operation_key=request.idempotency_key,  # idempotency replay gate
        response_model=AttemptCompleteResponse,
        runner=_runner,
        upload_folder=get_upload_folder(),
    )
