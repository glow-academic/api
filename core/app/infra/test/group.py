"""Test group logic — time-windowed artifact grouping + orchestration.

Canonical infra function for resolving or creating test groups.
Per-artifact, Redis-backed sliding window. Also supports explicit
group naming, replacing the need for the centralized group/name.py.

Flow:
  1. resolve_profile_identity_context -> profile
  2. Resolve group: existing (by group_id or Redis window) or create fresh
  3. Optional: create group_names_entry
  4. Refresh MVs + invalidate cache (only when something was written)
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.globals import get_pool
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.websocket.socket_event import make_emit
from app.infra.websocket.test_events_impl import test_group_impl
from app.tools.entries.group_names.create import create_group_name
from app.tools.entries.group_names.refresh import refresh_group_names
from app.tools.entries.groups.create import create_group
from app.tools.entries.groups.refresh import refresh_groups
from app.utils.cache.invalidate_tags import invalidate_tags

ARTIFACT_TYPE = "test"
DEFAULT_WINDOW_SECONDS = 60


def _redis_key(profile_id: UUID) -> str:
    return f"artifact_group:{ARTIFACT_TYPE}:{profile_id}"


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class GroupTestApiRequest(BaseModel):
    """Request model for test group endpoint."""

    group_id: UUID | None = Field(
        None,
        description="Existing group UUID (omit to create or reuse via time window)",
    )
    name: str | None = Field(None, description="Optional name for the group")


class GroupTestApiResponse(BaseModel):
    """Response model for test group endpoint."""

    group_id: UUID = Field(
        ..., description="Resolved or newly created group UUID"
    )
    group_name_id: UUID | None = Field(
        None,
        description="UUID of the created group_names entry (if name was provided)",
    )
    name: str | None = Field(
        None, description="The name that was set (if provided)"
    )


# ---------------------------------------------------------------------------
# Time-windowed artifact grouping impl
# ---------------------------------------------------------------------------


async def group_test_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: GroupTestApiRequest | None = None,
    group_id: UUID | None = None,
    name: str | None = None,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
) -> GroupTestApiResponse:
    """Resolve or create a test group with optional naming.

    Behavior:
      - group_id omitted -> check Redis for active time-windowed group;
        create new groups_entry if none found.
      - group_id provided -> use it directly and refresh the window.
      - name provided -> create group_names_entry for the resolved group.

    Accepts either a GroupTestApiRequest (HTTP/WS) or kwargs (internal).
    """
    # Unpack request if provided
    if request is not None:
        group_id = request.group_id
        name = request.name

    # -- Step 1: Profile context -------------------------------------------

    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Resolve or create group -----------------------------------

    resolved_group_id: UUID
    created_new = False

    if group_id is not None:
        resolved_group_id = group_id
        # Refresh the window since this group is still active
        await redis.setex(
            _redis_key(profile_id), window_seconds, str(group_id),
        )
    else:
        # Check Redis time window
        key = _redis_key(profile_id)
        existing = await redis.get(key)
        if existing:
            resolved_group_id = UUID(
                existing.decode() if isinstance(existing, bytes) else existing
            )
            await redis.expire(key, window_seconds)
        else:
            async with pool.acquire() as conn:
                result = await create_group(conn, session_id=session_id, artifact_type=ARTIFACT_TYPE)
            resolved_group_id = result.id
            await redis.setex(key, window_seconds, str(resolved_group_id))
            created_new = True

    # -- Step 3: Optional naming -------------------------------------------

    group_name_id: UUID | None = None
    if name:
        async with pool.acquire() as conn:
            name_result = await create_group_name(
                conn,
                group_id=resolved_group_id,
                name=name,
                session_id=session_id,
            )
            group_name_id = name_result.id

        # Refresh MVs
        async with pool.acquire() as conn:
            await refresh_group_names(conn)
            await refresh_groups(conn)

    # -- Step 4: Invalidate cache (only if we wrote something) -------------

    if created_new or group_name_id:
        await invalidate_tags(["groups"], redis=redis)

    return GroupTestApiResponse(
        group_id=resolved_group_id,
        group_name_id=group_name_id,
        name=name,
    )


# ---------------------------------------------------------------------------
# Orchestration handler (sequential test runs in a group)
# ---------------------------------------------------------------------------


async def test_group_internal_impl(data: dict[str, Any], *, emit=None) -> None:
    """Run canonical test group orchestration for any surface."""
    await test_group_impl(data, emit=emit or make_emit(), pool=get_pool())
