"""Invocation key decrypt endpoint — thin route, delegates to infra.

Scoped authorization: validates the key belongs to the invocation before decrypting.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.globals import get_pool, get_redis_client
from app.infra.identity.decrypt import resolve_decrypt
from app.infra.invocation.types import (
    DecryptInvocationKeyApiRequest,
    DecryptInvocationKeyApiResponse,
)
from app.tools.entries.invocation.get import get_invocations
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
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"
        pool = get_pool()
        redis = get_redis_client()

        # Validate key belongs to this invocation
        async with pool.acquire() as conn:
            invocations = await get_invocations(conn, [request.invocation_id])

        if not invocations:
            raise HTTPException(status_code=404, detail="Invocation not found")

        invocation = invocations[0]
        if request.key_id not in (invocation.key_ids or []):
            raise HTTPException(
                status_code=403,
                detail="Key does not belong to this invocation",
            )

        result = await resolve_decrypt(
            pool,
            redis,
            profile_id=profile_id,
            key_id=request.key_id,
            bypass_cache=bypass_cache,
        )

        return DecryptInvocationKeyApiResponse(
            key=result.key,
            name=result.name,
            actor_name=result.actor_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="decrypt_invocation_key",
            request=http_request,
        )
