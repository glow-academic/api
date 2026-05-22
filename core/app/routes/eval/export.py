"""Eval export endpoint — composable infra architecture."""

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.infra.eval.export import export_eval_impl
from app.infra.eval.group import group_eval_impl
from app.infra.eval.types import ExportEvalApiResponse
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder

router = APIRouter()


class ExportEvalApiRequest(BaseModel):
    """Request model for eval export."""

    eval_id: UUID | None = None
    idempotency_key: UUID | None = Field(None, description="Idempotency key — replays the prior export instead of re-running")


@router.post("/export", response_model=ExportEvalApiResponse)
async def export_evals(
    body: ExportEvalApiRequest,
    http_request: Request,
) -> ExportEvalApiResponse:
    """Export all evals as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    session_id = http_request.state.session_id
    pool = get_pool()
    redis = get_redis_client()

    # Resolve time-windowed group for audit linking
    group_id = None
    if session_id:
        group_result = await group_eval_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            id_only=True,
        )
        group_id = group_result.group_id

    async def _runner() -> ExportEvalApiResponse:
        return await export_eval_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            eval_id=body.eval_id,
        )

    return await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="eval",
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        operation="export",
        arguments=body.model_dump(mode="json"),
        response_model=ExportEvalApiResponse,
        runner=_runner,
        upload_folder=get_upload_folder(),
        operation_key=body.idempotency_key,  # idempotency replay gate
    )
