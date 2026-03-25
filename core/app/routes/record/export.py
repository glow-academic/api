"""Record export endpoint — composable infra architecture."""

from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from app.infra.globals import get_pool, get_redis_client
from app.infra.record_export import export_record_client
from app.infra.record.types import ExportRecordApiResponse

router = APIRouter()


class ExportRecordApiRequest(BaseModel):
    target_profile_id: UUID


@router.post("/export", response_model=ExportRecordApiResponse)
async def export_record(
    body: ExportRecordApiRequest,
    http_request: Request,
    response: Response,
) -> ExportRecordApiResponse:
    """Export record data (dashboard for one profile) as a clean, denormalized ZIP."""
    pool = get_pool()
    redis = get_redis_client()
    profile_id = http_request.state.profile_id

    return await export_record_client(
        pool,
        redis,
        profile_id=profile_id,
        target_profile_id=body.target_profile_id,
    )
