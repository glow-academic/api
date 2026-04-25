"""Provider decrypt logic — composable infra architecture.

Validates the key belongs to the provider, then delegates to resolve_decrypt.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.identity.decrypt import resolve_decrypt
from app.infra.provider.types import DecryptProviderKeyApiResponse
from app.tools.artifacts.provider.get import get_providers


async def decrypt_provider_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    provider_id: UUID,
    key_id: UUID,
    bypass_cache: bool = False,
) -> DecryptProviderKeyApiResponse:
    """Decrypt a key scoped to a provider artifact.

    Flow:
      1. Validate the key belongs to the provider (get_providers with keys=True)
      2. resolve_decrypt — profile identity check + actual decryption
      3. Return typed response
    """
    # ── Step 1: Validate key belongs to provider ──────────────────────
    providers = await get_providers(pool, [provider_id], keys=True, active=None)

    if not providers:
        raise HTTPException(status_code=404, detail="Provider not found")

    provider = providers[0]
    if key_id not in (provider.key_ids or []):
        raise HTTPException(
            status_code=403,
            detail="Key does not belong to this provider",
        )

    # ── Step 2: Decrypt ───────────────────────────────────────────────
    result = await resolve_decrypt(
        pool,
        redis,
        profile_id=profile_id,
        key_id=key_id,
        bypass_cache=bypass_cache,
    )

    return DecryptProviderKeyApiResponse(
        key=result.key,
        name=result.name,
        actor_name=result.actor_name,
    )
