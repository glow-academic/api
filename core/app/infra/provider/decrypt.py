"""Provider decrypt logic — composable infra architecture.

Validates the caller's permission and that the key belongs to the
provider, then delegates to resolve_decrypt.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.identity.decrypt import resolve_decrypt
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
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
    """Decrypt (reveal) a key scoped to a provider artifact.

    Flow:
      1. Authorize — caller must hold the provider:update permission
         (revealing a raw API key is a privileged read tied to the
         admin-only provider edit page where the reveal button lives).
      2. Validate the key belongs to the provider (get_providers with keys=True)
      3. resolve_decrypt — profile identity check + actual decryption
      4. Return typed response
    """
    # ── Step 1: Authorize the caller ──────────────────────────────────
    # The route/WS layer only guarantees an *authenticated* profile; it
    # does NOT gate by role. Without this check any signed-in user (Guest,
    # student/UTA, etc.) could reveal a provider's raw API-key secret.
    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, bypass_cache=bypass_cache
    )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )
    if not has_permission(profile.role_permissions, "provider", "update"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to reveal provider keys.",
        )

    # ── Step 2: Validate key belongs to provider ──────────────────────
    providers = await get_providers(pool, [provider_id], keys=True, active=None)

    if not providers:
        raise HTTPException(status_code=404, detail="Provider not found")

    provider = providers[0]
    if key_id not in (provider.key_ids or []):
        raise HTTPException(
            status_code=403,
            detail="Key does not belong to this provider",
        )

    # ── Step 3: Decrypt ───────────────────────────────────────────────
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
