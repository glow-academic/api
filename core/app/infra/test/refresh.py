"""Test refresh logic — composable infra architecture.

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
from app.tools.entries.calls.refresh import refresh_calls_internal
from app.tools.entries.messages.refresh import refresh_messages_internal
from app.tools.entries.runs.refresh import refresh_runs_internal
from app.tools.entries.test.refresh import refresh_test

# Tags to invalidate — artifact cache + resource caches
_TAGS = ["test", "artifacts"]

# Views refreshed by this endpoint
_VIEWS = ["test_mv", "runs_mv", "messages_mv", "calls_mv"]


async def refresh_test_impl(
    pool: asyncpg.Pool,
    redis: Redis | None,
    *,
    profile_id: UUID,
) -> RefreshResponse:
    """Test refresh using composable infra functions.

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

    async def _refresh_test() -> None:
        async with pool.acquire() as conn:
            await refresh_test(conn)

    async def _refresh_runs() -> None:
        async with pool.acquire() as conn:
            await refresh_runs_internal(conn, redis=redis)

    async def _refresh_messages() -> None:
        async with pool.acquire() as conn:
            await refresh_messages_internal(conn, redis=redis)

    async def _refresh_calls() -> None:
        async with pool.acquire() as conn:
            await refresh_calls_internal(conn, redis=redis)

    await asyncio.gather(
        _refresh_test(),
        _refresh_runs(),
        _refresh_messages(),
        _refresh_calls(),
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
