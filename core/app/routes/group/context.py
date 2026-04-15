"""Group context endpoint — page bootstrap with docs + profile + permissions."""

from fastapi import APIRouter, Request, Response

from app.infra.docs.types import ComposedContextResponse
from app.infra.docs_helper import DocsApiRequest
from app.infra.globals import get_pool, get_redis_client
from app.infra.group.page_context import page_context_group_impl

router = APIRouter()


@router.post("/context", response_model=ComposedContextResponse)
async def get_group_context(
    body: DocsApiRequest,
    http_request: Request,
    response: Response,
) -> ComposedContextResponse:
    """Get page context for the group analytics.

    Returns docs + profile identity + evaluated permissions in a single call.
    Superset of /docs — clients can migrate from /docs to /context incrementally.
    """
    pool = get_pool()
    profile_id = http_request.state.profile_id
    result = await page_context_group_impl(
        pool,
        get_redis_client(),
        profile_id=profile_id,
        entity_id=body.entity_id,
    )
    response.headers["X-Cache-Tags"] = "groups"
    return result
