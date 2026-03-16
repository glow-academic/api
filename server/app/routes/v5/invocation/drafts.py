"""Invocation drafts list endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.invocation.drafts.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.globals import get_pool, get_redis_client
from app.infra.invocation.drafts import list_invocation_drafts_impl
from app.infra.invocation.types import GetInvocationDraftsApiResponse
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/drafts", response_model=GetInvocationDraftsApiResponse)
async def get_invocation_drafts(
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

        pool = get_pool()
        redis = get_redis_client()
        bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"

        context = await list_invocation_drafts_impl(
            pool,
            redis,
            profile_id=UUID(profile_id),
            bypass_cache=bypass_cache,
        )

        response.headers["X-Cache-Tags"] = "invocation,drafts"
        return GetInvocationDraftsApiResponse(
            entries=context.entries.get("drafts"),
        )

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
