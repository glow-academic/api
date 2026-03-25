"""Attempt export endpoint — composable infra architecture."""

from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from app.infra.attempt.export import export_attempt_impl
from app.infra.globals import get_pool, get_redis_client
from app.infra.attempt.types import ExportAttemptApiResponse

router = APIRouter()


class ExportAttemptApiRequest(BaseModel):
    attempt_id: UUID


@router.post("/export", response_model=ExportAttemptApiResponse)
async def export_attempt(
    body: ExportAttemptApiRequest,
    http_request: Request,
    response: Response,
) -> ExportAttemptApiResponse:
    """Export attempt data as a clean, denormalized ZIP."""
    profile_id = http_request.state.profile_id
    pool = get_pool()
    redis = get_redis_client()

    return await export_attempt_impl(
        pool,
        redis,
        profile_id=profile_id,
        attempt_id=body.attempt_id,
    )
