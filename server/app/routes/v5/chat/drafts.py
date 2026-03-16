"""Chat drafts list endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.chat.drafts.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.chat.drafts import list_chat_drafts_impl
from app.infra.globals import get_pool, get_redis_client
from app.infra.chat.types import GetChatDraftsApiResponse
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/drafts", response_model=GetChatDraftsApiResponse)
async def get_chat_drafts(
    http_request: Request,
    response: Response,
) -> GetChatDraftsApiResponse:
    """List chat drafts owned by the current profile."""
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

        context = await list_chat_drafts_impl(
            pool,
            redis,
            profile_id=UUID(profile_id),
            bypass_cache=bypass_cache,
        )

        response.headers["X-Cache-Tags"] = "chats,drafts"
        return GetChatDraftsApiResponse(
            entries=context.entries.get("drafts"),
        )

    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="get_chat_drafts",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
