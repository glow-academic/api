"""Dashboard refresh logic — composable infra architecture.

Dashboard has no entry refresh tools — only permission check and cache invalidation.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.refresh.types import RefreshResponse

# Tags to invalidate — artifact cache + resource caches
_TAGS = ["dashboard", "artifacts"]

# Views refreshed by this endpoint (none for dashboard)
_VIEWS: list[str] = []


async def refresh_dashboard_impl(
    pool: asyncpg.Pool,
    redis: Redis | None,
    *,
    profile_id: UUID,
) -> RefreshResponse:
    """Dashboard refresh using composable infra functions.

    Flow:
      1. resolve_profile_identity_context — permission check
      2. Invalidate cache tags (no MVs to refresh)
    """
    from fastapi import HTTPException

    # -- Step 1: Permission check ------------------------------------------

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Invalidate cache tags -------------------------------------

    if redis is not None:
        from app.utils.cache.invalidate_tags import invalidate_tags

        await invalidate_tags(_TAGS, redis=redis)

    return RefreshResponse(
        success=True,
        refreshed_views=_VIEWS,
        invalidated_tags=_TAGS,
    )
