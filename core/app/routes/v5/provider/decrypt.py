"""Provider key decrypt endpoint — thin route, delegates to infra.

Scoped authorization: validates the key belongs to the provider before decrypting.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.globals import get_pool, get_redis_client
from app.infra.identity.decrypt import resolve_decrypt
from app.infra.provider.types import (
    DecryptProviderKeyApiRequest,
    DecryptProviderKeyApiResponse,
)
from app.tools.artifacts.provider.get import get_providers
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/decrypt", response_model=DecryptProviderKeyApiResponse)
async def decrypt_provider_key(
    request: DecryptProviderKeyApiRequest,
    http_request: Request,
    response: Response,
) -> DecryptProviderKeyApiResponse:
    """Decrypt a key scoped to a provider artifact."""
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

        # Validate key belongs to this provider
        async with pool.acquire() as conn:
            providers = await get_providers(
                conn, [request.provider_id], keys=True, active=None
            )

        if not providers:
            raise HTTPException(status_code=404, detail="Provider not found")

        provider = providers[0]
        if request.key_id not in (provider.key_ids or []):
            raise HTTPException(
                status_code=403,
                detail="Key does not belong to this provider",
            )

        result = await resolve_decrypt(
            pool,
            redis,
            profile_id=profile_id,
            key_id=request.key_id,
            bypass_cache=bypass_cache,
        )

        return DecryptProviderKeyApiResponse(
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
            operation="decrypt_provider_key",
            request=http_request,
        )
