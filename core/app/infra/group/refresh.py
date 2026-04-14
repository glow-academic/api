"""Group refresh logic — composable infra architecture.

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
from app.tools.entries.group_names.refresh import refresh_group_names
from app.tools.entries.groups.refresh import refresh_groups

# Tags to invalidate — artifact cache + resource caches
_TAGS = ["groups", "artifacts"]

# Views refreshed by this endpoint
_VIEWS = ["groups_mv", "group_names_mv"]


async def refresh_group_impl(
    pool: asyncpg.Pool,
    redis: Redis | None,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **_kwargs,
) -> RefreshResponse:
    """Group refresh using composable infra functions.

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

    async def _refresh_groups() -> None:
        async with pool.acquire() as conn:
            await refresh_groups(conn)

    async def _refresh_group_names() -> None:
        async with pool.acquire() as conn:
            await refresh_group_names(conn)

    await asyncio.gather(
        _refresh_groups(),
        _refresh_group_names(),
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
