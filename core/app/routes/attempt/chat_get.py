"""Chat bundle artifact endpoint — thin HTTP adapter over the canonical shared operation."""

from __future__ import annotations

from typing import cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from app.infra.attempt.chat.get import get_chat_impl
from app.infra.attempt.chat.types import (
    GetChatRequest,
    GetChatResponse,
)
from app.infra.attempt.group import group_attempt_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


# =============================================================================
# Route Handler
# =============================================================================


@router.post("/chat_get", response_model=GetChatResponse)
async def chat_get(
    request: GetChatRequest,
    http_request: Request,
) -> GetChatResponse:
    """Get hydrated resources for chat bundle customization."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"
        pool = get_pool()
        redis = get_redis_client()

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_attempt_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                id_only=True,
            )
            group_id = group_result.group_id

        async def _runner() -> GetChatResponse:
            return await get_chat_impl(
                pool,
                redis,
                profile_id=cast(UUID, profile_id),
                session_id=cast(UUID, session_id),
                request=request,
                bypass_cache=bypass_cache,
            )

        return await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="attempt",
            profile_id=cast(UUID, profile_id),
            session_id=cast(UUID, session_id),
            group_id=group_id,
            operation="chat_get",
            arguments=request.model_dump(mode="json"),
            bypass_cache=bypass_cache,
            response_model=GetChatResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
            operation_key=request.snapshot_key,  # read snapshot
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="chat_get",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
