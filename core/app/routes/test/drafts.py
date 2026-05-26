"""Invocation drafts list endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.invocation.drafts.
Routed through the audit wrapper so ``snapshot_key`` replays a consistent view.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.invocation.drafts import list_invocation_drafts_impl
from app.infra.invocation.types import (
    GetInvocationDraftsApiRequest,
    GetInvocationDraftsApiResponse,
)
from app.infra.test.group import group_test_impl
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/drafts", response_model=GetInvocationDraftsApiResponse)
async def get_invocation_drafts(
    request: GetInvocationDraftsApiRequest,
    http_request: Request,
    response: Response,
) -> GetInvocationDraftsApiResponse:
    """List invocation drafts owned by the current profile."""
    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        session_id = http_request.state.session_id
        pool = get_pool()
        redis = get_redis_client()
        bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"

        group_id = None
        if session_id:
            group_result = await group_test_impl(
                pool, redis, profile_id=UUID(str(profile_id)), session_id=session_id,
                id_only=True,
            )
            group_id = group_result.group_id

        async def _runner() -> GetInvocationDraftsApiResponse:
            return await list_invocation_drafts_impl(
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
            artifact="test",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="drafts",
            arguments=request.model_dump(mode="json"),
            bypass_cache=bypass_cache,
            response_model=GetInvocationDraftsApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
            operation_key=request.snapshot_key,  # read snapshot: replay this view if echoed
        )

        response.headers["X-Cache-Tags"] = "invocation,drafts"
        return result

    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="get_invocation_drafts",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
