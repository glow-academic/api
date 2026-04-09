"""Profile unemulate logic — composable infra architecture.

Consumes the innermost emulation grant to peel one layer.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.identity.emulate import resolve_unemulation
from app.infra.profile.types import UnemulateProfileApiResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def unemulate_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    actor_profile_id: UUID | None = None,
) -> UnemulateProfileApiResponse:
    """Exit the innermost emulation layer.

    Raises HTTPException(400) if unemulation fails.
    Invalidates profile cache tags on success.
    """
    origin = actor_profile_id or profile_id

    result = await resolve_unemulation(pool, actor_profile_id=origin)

    if not result.ok:
        raise HTTPException(
            status_code=400, detail=result.reason or "Cannot exit emulation"
        )

    tags = ["profile"]
    await invalidate_tags(tags, redis=redis)

    return UnemulateProfileApiResponse(ok=result.ok, reason=result.reason)
