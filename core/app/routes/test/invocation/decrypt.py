"""Invocation key decrypt endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.invocation.decrypt.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.invocation.decrypt import decrypt_invocation_impl
from app.infra.test.group import group_test_impl
from app.infra.invocation.types import (
    DecryptInvocationKeyApiRequest,
    DecryptInvocationKeyApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/decrypt", response_model=DecryptInvocationKeyApiResponse)
async def decrypt_invocation_key(
    request: DecryptInvocationKeyApiRequest,
    http_request: Request,
    response: Response,
) -> DecryptInvocationKeyApiResponse:
    """Decrypt a key scoped to an invocation entry."""
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
            group_result = await group_test_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
            )
            group_id = group_result.group_id

        async def _runner() -> DecryptInvocationKeyApiResponse:
            return await decrypt_invocation_impl(
                pool,
                redis,
                profile_id=profile_id,
                invocation_id=request.invocation_id,
                key_id=request.key_id,
                bypass_cache=bypass_cache,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="invocation",
            operation="decrypt",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            arguments=request.model_dump(mode="json"),
            runner=_runner,
            upload_folder=get_upload_folder(),
            response_model=DecryptInvocationKeyApiResponse,
        )

        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="decrypt_invocation_key",
            request=http_request,
        )
