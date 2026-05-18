"""Attempt context endpoint — page bootstrap with docs + profile + permissions."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.infra.attempt.page_context import page_context_attempt_impl
from app.infra.docs.types import ComposedContextResponse
from app.infra.docs_helper import DocsApiRequest
from app.infra.globals import get_pool, get_redis_client

router = APIRouter()


@router.post("/context", response_model=ComposedContextResponse)
async def get_attempt_context(
    body: DocsApiRequest,
    http_request: Request,
    response: Response,
) -> ComposedContextResponse:
    """Get page context for the attempt artifact.

    Returns docs + profile identity + evaluated permissions in a single call.
    Superset of /docs — clients can migrate from /docs to /context incrementally.
    """
    profile_id = http_request.state.profile_id
    pool = get_pool()
    redis = get_redis_client()

    result = await page_context_attempt_impl(
        pool,
        redis,
        profile_id=profile_id,
        entity_id=body.entity_id,
    )

    response.headers["X-Cache-Tags"] = "attempts"
    return result
