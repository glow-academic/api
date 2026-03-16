"""Test export endpoint — composable infra architecture."""

from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from app.infra.globals import get_pool, get_redis_client
from app.infra.test.export import export_test_impl
from app.infra.test.types import ExportTestApiResponse

router = APIRouter()


class ExportTestApiRequest(BaseModel):
    test_id: UUID


@router.post("/export", response_model=ExportTestApiResponse)
async def export_test(
    body: ExportTestApiRequest,
    http_request: Request,
    response: Response,
) -> ExportTestApiResponse:
    """Export test data as a clean, denormalized ZIP."""
    profile_id = http_request.state.profile_id
    pool = get_pool()

    return await export_test_impl(
        pool,
        get_redis_client(),
        profile_id=profile_id,
        test_id=body.test_id,
    )
