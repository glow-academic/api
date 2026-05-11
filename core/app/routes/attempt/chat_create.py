"""Attempt chat create endpoint — thin HTTP adapter.

POST /attempt/chat/create — creates an attempt_chat from a chat template.
Core logic lives in app.infra.attempt.chat_create.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.infra.attempt.chat_create import (
    CreateAttemptChatApiRequest,
    CreateAttemptChatApiResponse,
    create_attempt_chat_impl,
)
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/chat_create", response_model=CreateAttemptChatApiResponse)
async def create_attempt_chat_endpoint(
    request: CreateAttemptChatApiRequest,
    http_request: Request,
) -> CreateAttemptChatApiResponse:
    """Create a chat within an attempt."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(status_code=401, detail="Profile ID is required. Please sign in again.")
        if not session_id:
            raise HTTPException(status_code=401, detail="Session ID is required. Please sign in again.")

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> CreateAttemptChatApiResponse:
            return await create_attempt_chat_impl(
                pool, redis,
                profile_id=profile_id,
                session_id=session_id,
                request=request,
            )

        return await run_artifact_operation_with_audit(
            pool, redis,
            artifact="attempt",
            profile_id=profile_id,
            session_id=session_id,
            operation="chat_create",
            arguments=request.model_dump(mode="json"),
            response_model=CreateAttemptChatApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="create_attempt_chat",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
