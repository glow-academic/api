"""System group logic — time-windowed artifact grouping.

Canonical infra function for resolving or creating system groups.
Per-artifact, Redis-backed sliding window. Also supports explicit
group naming, replacing the need for the centralized group/name.py.

Flow:
  1. resolve_profile_identity_context -> profile
  2. Resolve group: existing (by group_id or Redis window) or create fresh
  3. Optional: create group_names_entry
  4. Refresh MVs + invalidate cache (only when something was written)
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.group.refresh import refresh_group_impl
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.group_names.create import create_group_name
from app.tools.entries.groups.create import create_group

ARTIFACT_TYPE = "system"
DEFAULT_WINDOW_SECONDS = 60


def _redis_key(profile_id: UUID) -> str:
    return f"artifact_group:{ARTIFACT_TYPE}:{profile_id}"


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class GroupSystemApiRequest(BaseModel):
    """Request model for system group endpoint."""

    group_id: UUID | None = Field(
        None,
        description="Existing group UUID (omit to create or reuse via time window)",
    )
    name: str | None = Field(None, description="Optional name for the group")


class GroupSystemApiResponse(BaseModel):
    """Response model for system group endpoint."""

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
# Impl
# ---------------------------------------------------------------------------


async def group_system_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: GroupSystemApiRequest | None = None,
    group_id: UUID | None = None,
    name: str | None = None,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
    **_kwargs,
) -> GroupSystemApiResponse:
    """Resolve or create a system group with optional naming.

    Behavior:
      - group_id omitted -> check Redis for active time-windowed group;
        create new groups_entry if none found.
      - group_id provided -> use it directly and refresh the window.
      - name provided -> create group_names_entry for the resolved group.

    Accepts either a GroupSystemApiRequest (HTTP/WS) or kwargs (internal).
    """
    # Unpack request if provided
    if request is not None:
        group_id = request.group_id
        name = request.name

    # -- Step 1: Profile context ------------------------------------------------

    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Resolve or create group ----------------------------------------

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

    # -- Step 3: Optional naming ------------------------------------------------

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

    # -- Step 4: Refresh MVs + invalidate cache ---------------------------------

    if created_new or group_name_id:
        await refresh_group_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
        )

    return GroupSystemApiResponse(
        group_id=resolved_group_id,
        group_name_id=group_name_id,
        name=name,
    )
