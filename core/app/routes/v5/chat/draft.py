"""Chat draft endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.chat.draft.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.chat.draft import patch_chat_draft_impl
from app.infra.globals import get_pool, get_redis_client
from app.infra.chat.types import (
    PatchChatDraftApiRequest,
    PatchChatDraftApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.patch(
    "/draft",
    response_model=PatchChatDraftApiResponse,
)
async def patch_chat_draft(
    request: PatchChatDraftApiRequest,
    http_request: Request,
    response: Response,
) -> PatchChatDraftApiResponse:
    """Patch chat draft — composable infra architecture."""
    tags = ["training", "drafts"]

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
        result = await patch_chat_draft_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            request=request,
        )

        response.headers["X-Invalidate-Tags"] = ",".join(tags)
        return result
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="patch_chat_draft",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
