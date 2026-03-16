"""Chat refresh logic — composable infra architecture.

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
from app.tools.entries.chat.refresh import refresh_chat
from app.tools.entries.chat_drafts.refresh import refresh_chat_drafts

# Tags to invalidate — artifact cache + resource caches
_TAGS = ["chat", "artifacts"]

# Views refreshed by this endpoint
_VIEWS = ["chat_mv", "chat_drafts_mv"]


async def refresh_chat_impl(
    pool: asyncpg.Pool,
    redis: Redis | None,
    *,
    profile_id: UUID,
) -> RefreshResponse:
    """Chat refresh using composable infra functions.

    Flow:
      1. resolve_profile_identity_context — permission check
      2. Parallel refresh of dependent entry MVs
      3. Invalidate cache tags
    """
    from fastapi import HTTPException

    # -- Step 1: Permission check ------------------------------------------

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Parallel refresh of dependent entry MVs -------------------

    async def _refresh_chat() -> None:
        async with pool.acquire() as conn:
            await refresh_chat(conn)

    async def _refresh_chat_drafts() -> None:
        async with pool.acquire() as conn:
            await refresh_chat_drafts(conn)

    await asyncio.gather(
        _refresh_chat(),
        _refresh_chat_drafts(),
    )

    # -- Step 3: Invalidate cache tags -------------------------------------

    if redis is not None:
        from app.utils.cache.invalidate_tags import invalidate_tags

        await invalidate_tags(_TAGS, redis=redis)

    return RefreshResponse(
        success=True,
        refreshed_views=_VIEWS,
        invalidated_tags=_TAGS,
    )
