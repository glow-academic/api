"""Setting key decrypt endpoint — thin route, delegates to infra.

Scoped authorization: validates the key belongs to the setting
(as a provider_key or auth_item_key) before decrypting.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.globals import get_pool, get_redis_client
from app.infra.identity.decrypt import resolve_decrypt
from app.infra.setting.types import (
    DecryptSettingKeyApiRequest,
    DecryptSettingKeyApiResponse,
)
from app.tools.artifacts.setting.get import get_settings
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/decrypt", response_model=DecryptSettingKeyApiResponse)
async def decrypt_setting_key(
    request: DecryptSettingKeyApiRequest,
    http_request: Request,
    response: Response,
) -> DecryptSettingKeyApiResponse:
    """Decrypt a key scoped to a setting artifact."""
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

        # Validate key belongs to this setting (provider_keys or auth_item_keys)
        async with pool.acquire() as conn:
            settings = await get_settings(
                conn,
                [request.setting_id],
                provider_keys=True,
                auth_item_keys=True,
                active=None,
            )

        if not settings:
            raise HTTPException(status_code=404, detail="Setting not found")

        setting = settings[0]
        all_key_ids = list(setting.provider_key_ids or []) + list(
            setting.auth_item_keys_ids or []
        )
        if request.key_id not in all_key_ids:
            raise HTTPException(
                status_code=403,
                detail="Key does not belong to this setting",
            )

        result = await resolve_decrypt(
            pool,
            redis,
            profile_id=profile_id,
            key_id=request.key_id,
            bypass_cache=bypass_cache,
        )

        return DecryptSettingKeyApiResponse(
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
            operation="decrypt_setting_key",
            request=http_request,
        )
