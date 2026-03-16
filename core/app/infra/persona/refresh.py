"""Persona refresh logic — composable infra architecture.

Composes black-box entry refresh tools to refresh dependent MVs,
then invalidates cache tags for the artifact and its resources.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.refresh.types import RefreshResponse

# Black-box entry refresh tools
from app.tools.entries.persona.refresh import refresh_persona_internal
from app.tools.entries.persona_drafts.refresh import refresh_persona_drafts

# Tags to invalidate — artifact cache + resource caches
_TAGS = ["personas", "artifacts"]

# Views refreshed by this endpoint
_VIEWS = ["personas_mv", "persona_drafts_mv"]


async def refresh_persona_impl(
    pool: asyncpg.Pool,
    redis: Redis | None,
    *,
    profile_id: UUID,
) -> RefreshResponse:
    """Persona refresh using composable infra functions.

    Flow:
      1. resolve_profile_identity_context — permission check
      2. Parallel refresh of dependent entry MVs
      3. Invalidate cache tags
    """
    from fastapi import HTTPException

    # ── Step 1: Permission check ─────────────────────────────────────────

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Parallel refresh of dependent entry MVs ──────────────────

    async def _refresh_persona() -> None:
        async with pool.acquire() as conn:
            await refresh_persona_internal(conn)

    async def _refresh_drafts() -> None:
        async with pool.acquire() as conn:
            await refresh_persona_drafts(conn)

    await asyncio.gather(
        _refresh_persona(),
        _refresh_drafts(),
    )

    # ── Step 3: Invalidate cache tags ────────────────────────────────────

    if redis is not None:
        from app.utils.cache.invalidate_tags import invalidate_tags

        await invalidate_tags(_TAGS, redis=redis)

    return RefreshResponse(
        success=True,
        refreshed_views=_VIEWS,
        invalidated_tags=_TAGS,
    )
