"""Setting decrypt logic — composable infra architecture.

Validates the key belongs to the setting (as provider_key or auth_item_key),
then delegates to resolve_decrypt.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.identity.decrypt import resolve_decrypt
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
      1. Validate the key belongs to the setting (provider_keys or auth_item_keys)
      2. resolve_decrypt — profile identity check + actual decryption
      3. Return typed response
    """
    # ── Step 1: Validate key belongs to setting ───────────────────────
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
