"""Setting decrypt logic — composable infra architecture.

Authorizes the caller, validates the key belongs to the setting (as
provider_key or auth_item_key), then delegates to resolve_decrypt.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.identity.decrypt import resolve_decrypt
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.infra.setting.types import DecryptSettingKeyApiResponse
from app.tools.artifacts.setting.get import get_settings


async def decrypt_setting_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    setting_id: UUID,
    key_id: UUID,
    bypass_cache: bool = False,
) -> DecryptSettingKeyApiResponse:
    """Decrypt a key scoped to a setting artifact.

    Flow:
      1. Authorize — caller must hold the setting:update permission
         (revealing a raw key is a privileged read tied to the setting
         edit page where the reveal action lives; compute_can_edit gates
         setting editing on this same permission).
      2. Validate the key belongs to the setting (provider_keys or auth_item_keys)
      3. resolve_decrypt — profile identity check + actual decryption
      4. Return typed response
    """
    # ── Step 1: Authorize the caller ──────────────────────────────────
    # The route/WS layer only guarantees an *authenticated* profile; it
    # does NOT gate by role. Without this check any signed-in user could
    # reveal a setting's raw secret (API key / auth item).
    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, bypass_cache=bypass_cache
    )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )
    if not has_permission(profile.role_permissions, "setting", "update"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to reveal setting keys.",
        )

    # ── Step 2: Validate key belongs to setting ───────────────────────
    with timed("query"):
        settings = await get_settings(
            pool,
            [setting_id],
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
    if key_id not in all_key_ids:
        raise HTTPException(
            status_code=403,
            detail="Key does not belong to this setting",
        )

    # ── Step 2: Decrypt ───────────────────────────────────────────────
    with timed("decrypt"):
        result = await resolve_decrypt(
            pool,
            redis,
            profile_id=profile_id,
            key_id=key_id,
            bypass_cache=bypass_cache,
        )

    return DecryptSettingKeyApiResponse(
        key=result.key,
        name=result.name,
        actor_name=result.actor_name,
    )
