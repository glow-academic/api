"""Group name endpoint — composable infra architecture.

Core logic for creating/updating group names via group_names_entry.
Thin route handler lives in app.routes.system.group.name.

Flow:
  1. resolve_profile_identity_context → profile (role, permissions)
  2. Validate group exists
  3. Create group_names_entry (append-only)
  4. Refresh MVs (group_names_mv → groups_mv)
  5. Invalidate cache
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.group_names.create import create_group_name
from app.tools.entries.group_names.refresh import refresh_group_names
from app.tools.entries.groups.refresh import refresh_groups
from app.utils.cache.invalidate_tags import invalidate_tags

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class NameGroupApiRequest(BaseModel):
    """Request model for group name endpoint."""

    group_id: UUID = Field(..., description="UUID of the group to name")
    name: str = Field(..., description="New name for the group")


class NameGroupApiResponse(BaseModel):
    """Response model for group name endpoint."""

    success: bool = Field(..., description="Whether the operation succeeded")
    group_name_id: UUID = Field(..., description="UUID of the created group_names entry")
    name: str = Field(..., description="The name that was set")


# ---------------------------------------------------------------------------
# Impl
# ---------------------------------------------------------------------------


async def name_group_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    group_id: UUID | None = None,
    name: str | None = None,
    request: NameGroupApiRequest | None = None,
    **kwargs: str,
) -> NameGroupApiResponse:
    """Set a group name using composable infra functions.

    Accepts either a NameGroupApiRequest (HTTP route) or kwargs (AI tool path).
    """
    # Build from kwargs if no request provided (AI tool path)
    if request is None:
        resolved_group_id = group_id or (UUID(kwargs["group_id"]) if "group_id" in kwargs else None)
        resolved_name = name or kwargs.get("name", "")
        if not resolved_group_id:
            raise HTTPException(status_code=400, detail="group_id is required")
        if not resolved_name:
            raise HTTPException(status_code=400, detail="name is required")
    else:
        resolved_group_id = request.group_id
        resolved_name = request.name

    # Step 1: Profile context
    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # Step 2: Create group_names entry (append-only)
    async with pool.acquire() as conn:
        result = await create_group_name(
            conn,
            redis, group_id=resolved_group_id,
            name=resolved_name,
            session_id=session_id,
        )

    # Step 3: Refresh MVs (group_names_mv → groups_mv)
    async with pool.acquire() as conn:
        await refresh_group_names(conn)
        await refresh_groups(conn)

    # Step 4: Invalidate cache
    await invalidate_tags(["groups"], redis=redis)

    return NameGroupApiResponse(
        success=True,
        group_name_id=result.id,
        name=resolved_name,
    )
