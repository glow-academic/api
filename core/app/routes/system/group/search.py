"""Group search endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.group.search.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.system.group import group_system_impl
from app.infra.group.search import search_group_impl
from app.infra.group.types import GetGroupListRequest, GetGroupListResponse
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/search", response_model=GetGroupListResponse)
async def search_groups(
    request: GetGroupListRequest,
    http_request: Request,
    response: Response,
) -> GetGroupListResponse:
    """Search groups — composable infra architecture."""
    tags = ["group"]

    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()
        session_id = getattr(http_request.state, "session_id", None)

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_system_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
            )
            group_id = group_result.group_id

        async def _runner() -> GetGroupListResponse:
            return await search_group_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                search=request.search,
                date_from=request.date_from,
                date_to=request.date_to,
                page_size=request.page_limit,
                page_offset=request.page_offset,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            artifact="system",
            operation="group_search",
            arguments=request.model_dump(mode="json"),
            response_model=GetGroupListResponse,
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
            operation="search_groups",
            request=http_request,
        )
