"""Session export endpoint — composable infra architecture."""

from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from app.infra.globals import get_pool, get_redis_client
from app.infra.session.export import export_session_impl
from app.infra.session.types import ExportSessionApiResponse

router = APIRouter()


class ExportSessionApiRequest(BaseModel):
    target_session_id: UUID


@router.post("/export", response_model=ExportSessionApiResponse)
async def export_session(
    body: ExportSessionApiRequest,
    http_request: Request,
    response: Response,
) -> ExportSessionApiResponse:
    """Export session data as a clean, denormalized ZIP."""
    profile_id = http_request.state.profile_id
    pool = get_pool()

    return await export_session_impl(
        pool,
        get_redis_client(),
        profile_id=profile_id,
        target_session_id=body.target_session_id,
    )
