"""Agent drafts list endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.agent.drafts.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.agent.drafts import list_agent_drafts_impl
from app.infra.agent.group import group_agent_impl
from app.infra.agent.types import (
    GetAgentDraftsApiRequest,
    GetAgentDraftsApiResponse,
)
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/drafts", response_model=GetAgentDraftsApiResponse)
async def get_agent_drafts(
    request: GetAgentDraftsApiRequest,
    http_request: Request,
    response: Response,
) -> GetAgentDraftsApiResponse:
    """List agent drafts owned by the current profile."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()
        bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_agent_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                id_only=True,
            )
            group_id = group_result.group_id

        async def _runner() -> GetAgentDraftsApiResponse:
            return await list_agent_drafts_impl(
                pool,
                redis,
                profile_id=UUID(profile_id),
                session_id=session_id,
                search=request.search,
                date_from=request.date_from,
                date_to=request.date_to,
                page_limit=request.page_limit,
                page_offset=request.page_offset,
                bypass_cache=bypass_cache,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="agent",
            profile_id=UUID(profile_id),
            session_id=session_id,
            group_id=group_id,
            operation="drafts",
            arguments={},
            bypass_cache=bypass_cache,
            response_model=GetAgentDraftsApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
            operation_key=request.snapshot_key,  # read snapshot: replay this view if echoed
        )
        response.headers["X-Cache-Tags"] = "agents,drafts"
        return result

    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="get_agent_drafts",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
