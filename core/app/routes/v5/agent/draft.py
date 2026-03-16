"""Agent draft endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.agent.draft.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.agent.draft import patch_agent_draft_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.agent.types import (
    PatchAgentDraftApiRequest,
    PatchAgentDraftApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.patch(
    "/draft",
    response_model=PatchAgentDraftApiResponse,
)
async def patch_agent_draft(
    request: PatchAgentDraftApiRequest,
    http_request: Request,
    response: Response,
) -> PatchAgentDraftApiResponse:
    """Patch agent draft — composable infra architecture."""
    tags = ["agents", "drafts"]

    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        session_id = http_request.state.session_id
        if not session_id:
            raise HTTPException(
                status_code=401,
                detail="Session ID is required.",
            )

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> PatchAgentDraftApiResponse:
            return await patch_agent_draft_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                request=request,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="agent",
            profile_id=profile_id,
            session_id=session_id,
            draft_id=request.input_draft_id,
            operation="draft",
            arguments=request.model_dump(mode="json"),
            response_model=PatchAgentDraftApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = ",".join(tags)
        return result
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="patch_agent_draft",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
