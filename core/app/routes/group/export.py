"""Group export endpoint — composable infra architecture."""

from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from app.infra.globals import get_pool, get_redis_client
from app.infra.group.export import export_group_impl
from app.infra.group.types import ExportGroupApiResponse

router = APIRouter()


class ExportGroupApiRequest(BaseModel):
    group_id: UUID


@router.post("/export", response_model=ExportGroupApiResponse)
async def export_group(
    body: ExportGroupApiRequest,
    http_request: Request,
    response: Response,
) -> ExportGroupApiResponse:
    """Export group data as a clean, denormalized ZIP."""
    pool = get_pool()
    profile_id = http_request.state.profile_id

    return await export_group_impl(
        pool,
        get_redis_client(),
        profile_id=profile_id,
        group_id=body.group_id,
    )
