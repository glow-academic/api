"""Setting context endpoint — page bootstrap with docs + profile + permissions."""

from fastapi import APIRouter, Request, Response

from app.infra.docs.types import ComposedContextResponse
from app.infra.docs_helper import DocsApiRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.setting.group import group_setting_impl
from app.infra.setting.page_context import page_context_setting_impl

router = APIRouter()


@router.post("/context", response_model=ComposedContextResponse)
async def get_setting_context(
    body: DocsApiRequest,
    http_request: Request,
    response: Response,
) -> ComposedContextResponse:
    """Get page context for the setting artifact.

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
        group_result = await group_setting_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
        )
        group_id = group_result.group_id

    async def _runner() -> ComposedContextResponse:
        return await page_context_setting_impl(
            pool,
            redis,
            profile_id=profile_id,
            entity_id=body.entity_id,
        )

    result = await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="setting",
        profile_id=profile_id,
        session_id=session_id,
        operation="context",
        arguments=body.model_dump(mode="json"),
        response_model=ComposedContextResponse,
        runner=_runner,
        upload_folder=get_upload_folder(),
        group_id=group_id,
    )

    response.headers["X-Cache-Tags"] = "settings"
    return result
