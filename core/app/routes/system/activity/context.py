"""Activity context endpoint — page bootstrap with docs + profile + permissions."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.infra.activity.group import group_activity_impl
from app.infra.activity.page_context import page_context_activity_impl
from app.infra.docs.types import ComposedContextResponse
from app.infra.docs_helper import DocsApiRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder

router = APIRouter()


@router.post("/context", response_model=ComposedContextResponse)
async def get_activity_context(
    body: DocsApiRequest,
    http_request: Request,
    response: Response,
) -> ComposedContextResponse:
    """Get page context for the activity artifact.

    Returns docs + profile identity + evaluated permissions in a single call.
    Superset of /docs — clients can migrate from /docs to /context incrementally.
    """
    profile_id = http_request.state.profile_id
    session_id = http_request.state.session_id
    pool = get_pool()
    redis = get_redis_client()

    # Resolve time-windowed group for audit linking
    group_id = None
    if session_id:
        group_result = await group_activity_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
        )
        group_id = group_result.group_id

    async def _runner() -> ComposedContextResponse:
        return await page_context_activity_impl(
            pool,
            redis,
            profile_id=profile_id,
            entity_id=body.entity_id,
        )

    result = await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="activity",
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        operation="context",
        arguments=body.model_dump(mode="json"),
        response_model=ComposedContextResponse,
        runner=_runner,
        upload_folder=get_upload_folder(),
    )

    response.headers["X-Cache-Tags"] = "activity"
    return result
