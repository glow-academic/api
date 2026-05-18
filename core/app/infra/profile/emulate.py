"""Profile emulate logic — composable infra architecture.

Creates an emulation grant. resolve_identity() picks it up on next request.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.identity.emulate import resolve_emulation
from app.infra.profile.types import EmulateProfileApiResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def emulate_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    target_profile_id: UUID,
    ttl_minutes: int = 120,
    bypass_cache: bool = False,
    actor_profile_id: UUID | None = None,
) -> EmulateProfileApiResponse:
    """Create an emulation grant for the given requester -> target pair.

    Raises HTTPException(403) if emulation is not allowed.
    Invalidates profile cache tags on success.
    """
    result = await resolve_emulation(
        pool,
        redis,
        requester_profile_id=profile_id,
        target_profile_id=target_profile_id,
        ttl_minutes=ttl_minutes,
        bypass_cache=bypass_cache,
        actor_profile_id=actor_profile_id,
    )

    if not result.allowed:
        raise HTTPException(status_code=403, detail=result.reason or "Forbidden")

    tags = ["profile"]
    await invalidate_tags(tags, redis=redis)

    return EmulateProfileApiResponse(
        allowed=result.allowed,
        reason=result.reason,
        grant_id=result.grant_id,
        expires_at=result.expires_at,
    )
