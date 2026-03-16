"""Eval export endpoint — composable infra architecture."""

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.infra.eval.export import export_eval_impl
from app.infra.globals import get_pool, get_redis_client
from app.infra.eval.types import ExportEvalApiResponse

router = APIRouter()


class ExportEvalApiRequest(BaseModel):
    """Request model for eval export."""

    eval_id: UUID | None = None


@router.post("/export", response_model=ExportEvalApiResponse)
async def export_evals(
    body: ExportEvalApiRequest,
    http_request: Request,
) -> ExportEvalApiResponse:
    """Export all evals as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    pool = get_pool()
    redis = get_redis_client()

    return await export_eval_impl(
        pool,
        redis,
        profile_id=profile_id,
        eval_id=body.eval_id,
    )
