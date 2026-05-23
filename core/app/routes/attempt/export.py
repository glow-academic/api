"""Attempt export endpoint — view-aware, canonical file-modality output.

Routed through the audit wrapper: idempotency replay (operation_key) + soft/accept
staging of the dormant export file chain (propose → accept activates).
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.attempt.export import export_attempt_impl
from app.infra.attempt.group import group_attempt_impl
from app.infra.attempt.types import ExportAttemptApiRequest, ExportAttemptApiResponse
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder

router = APIRouter()


@router.post("/export", response_model=ExportAttemptApiResponse)
async def export_attempt(
    body: ExportAttemptApiRequest,
    http_request: Request,
    response: Response,
) -> ExportAttemptApiResponse:
    """Artifact-level attempt export.

    Dispatches on ``body.view`` to per-view exports and returns
    ``{file_id, file_name, row_count}``. Client downloads via
    ``/api/attempt/download/{file_id}`` (BFF) → ``/attempt/file/download``.
    """
    profile_id = http_request.state.profile_id
    session_id = http_request.state.session_id
    pool = get_pool()
    redis = get_redis_client()

    # Resolve time-windowed group for audit linking.
    group_id = None
    if session_id:
        group_result = await group_attempt_impl(
            pool, redis, profile_id=UUID(str(profile_id)), session_id=session_id,
            id_only=True,
        )
        group_id = group_result.group_id

    is_ack = body.accept is not None and body.idempotency_key is not None

    # ``call_id`` threaded in by the wrapper (signature opt-in) — the
    # server-minted calls_entry id the soft ledger keys on.
    async def _runner(call_id: UUID | None = None) -> ExportAttemptApiResponse:
        return await export_attempt_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            view=body.view,
            attempt_id=body.attempt_id,
            record_id=body.record_id,
            mode=body.mode,
            soft=body.soft,
            accept=body.accept,
            idempotency_key=body.idempotency_key,
            call_id=call_id,
        )

    return await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="attempt",
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        operation="export",
        # On ack, carry only `accept` so the gate's _is_bare_ack skips it.
        arguments={"accept": body.accept} if is_ack else body.model_dump(mode="json"),
        operation_key=body.idempotency_key,  # idempotency replay gate
        response_model=ExportAttemptApiResponse,
        runner=_runner,
        upload_folder=get_upload_folder(),
    )
