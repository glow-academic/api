"""Group search logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments, name)
  2. search_groups — core MV search against groups_mv
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.group.types import (
    GetGroupListRequest,
    GetGroupListResponse,
    GroupListItem,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.groups.search import search_groups


async def search_group_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    search: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page_size: int = 20,
    page_offset: int = 0,
) -> GetGroupListResponse:
    """Group search using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, name
      2. search_groups → group items from groups_mv
    """
    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Search groups ──────────────────────────────────────────

    # Scope to the user's session if provided
    session_ids = [session_id] if session_id else None

    async with pool.acquire() as conn:
        results = await search_groups(
            conn,
            session_ids=session_ids,
            name=search,
            date_from=date_from,
            date_to=date_to,
            limit=page_size,
            offset=page_offset,
        )

    # ── Step 3: Build response ─────────────────────────────────────────

    items = [
        GroupListItem(
            group_id=r.id,
            session_id=r.session_id,
            group_name=r.name or None,
            first_run_at=r.created_at,
            last_run_at=r.created_at,
        )
        for r in results
    ]

    return GetGroupListResponse(
        actor_name=profile.name,
        items=items,
        total_count=len(items),
    )
