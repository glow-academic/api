"""Test invocation create endpoint — thin HTTP adapter.

POST /test/invocation/create — creates a test_invocation_entry on a test.
Used in the `use_custom` flow: when the workflow pauses on a custom-input
invocation, the client posts the user's selections here, then proceeds.

Mirrors POST /attempt/chat/create. Core logic lives in
app.infra.invocation.create.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.invocation.create import (
    CreateInvocationApiRequest,
    CreateInvocationApiResponse,
    create_invocation_impl,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/invocation_create", response_model=CreateInvocationApiResponse)
async def create_invocation_endpoint(
    request: CreateInvocationApiRequest,
    http_request: Request,
) -> CreateInvocationApiResponse:
    """Create an invocation within a test."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )
        if not session_id:
            raise HTTPException(
                status_code=401,
                detail="Session ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> CreateInvocationApiResponse:
            return await create_invocation_impl(
                pool, redis,
                profile_id=profile_id,
                session_id=session_id,
                request=request,
            )

        return await run_artifact_operation_with_audit(
            pool, redis,
            artifact="test",
            profile_id=profile_id,
            session_id=session_id,
            operation="invocation_create",
            arguments=request.model_dump(mode="json"),
            response_model=CreateInvocationApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="create_invocation",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
