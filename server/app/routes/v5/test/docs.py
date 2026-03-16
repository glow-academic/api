"""Test docs endpoint — composable infra architecture."""

from fastapi import APIRouter, Request, Response

from app.infra.docs.types import ComposedDocsResponse
from app.infra.docs_helper import DocsApiRequest
from app.infra.globals import get_pool, get_redis_client
from app.infra.test.docs import docs_test_impl

router = APIRouter()


@router.post("/docs", response_model=ComposedDocsResponse)
async def get_test_docs_endpoint(
    body: DocsApiRequest,
    http_request: Request,
    response: Response,
) -> ComposedDocsResponse:
    """Get composed documentation for the test analytics."""
    profile_id = http_request.state.profile_id
    pool = get_pool()

    return await docs_test_impl(
        pool,
        get_redis_client(),
        profile_id=profile_id,
        entity_id=body.entity_id,
    )
