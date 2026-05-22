"""POST /attempt/stop — routed through the audit wrapper (idempotency + soft/accept).

Baseline: idempotency replay (operation_key). Soft/accept (record-and-hold):
``soft=true`` stages the stop (records intent, doesn't cancel) for composing a
dormant benchmark scenario; the ack ({idempotency_key, accept}) performs/discards
it. ``soft=false`` cancels live (original behavior).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from app.infra.attempt.stop import (
    AttemptStopRequest,
    AttemptStopResponse,
    stop_attempt_impl,
)
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder

router = APIRouter()


@router.post("/stop", response_model=AttemptStopResponse)
async def attempt_stop(
    request: AttemptStopRequest,
    http_request: Request,
) -> AttemptStopResponse:
    profile_id_str = getattr(http_request.state, "profile_id", None)
    if not profile_id_str:
        raise HTTPException(status_code=401, detail="Missing profile")
    profile_id = UUID(profile_id_str)
    session_id = getattr(http_request.state, "session_id", None)
    pool = get_pool()
    redis = get_redis_client()

    is_ack = request.accept is not None and request.idempotency_key is not None

    # ``call_id`` is threaded in by the audit wrapper (signature opt-in) — the
    # server-minted calls_entry id the soft ledger keys on.
    async def _runner(call_id: UUID | None = None) -> AttemptStopResponse:
        return await stop_attempt_impl(
            pool,
            redis,
            profile_id=profile_id,
            group_id=request.group_id,
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
        group_id=request.group_id,
        operation="stop",
        # On ack, carry only `accept` so the gate's _is_bare_ack skips it.
        arguments={"accept": request.accept} if is_ack else request.model_dump(mode="json"),
        operation_key=request.idempotency_key,  # idempotency replay gate
        response_model=AttemptStopResponse,
        runner=_runner,
        upload_folder=get_upload_folder(),
    )
