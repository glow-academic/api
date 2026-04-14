"""Attempt generations logic — list generation groups for attempts.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, permissions)
  2. search_groups — core MV search with artifact_type="attempt" filter
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.attempt.types import (
    GenerationsAttemptApiResponse,
    GenerationsAttemptListItem,
)
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.groups.search import search_groups

ARTIFACT_TYPE = "attempt"


async def generations_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    search: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page_limit: int = 50,
    page_offset: int = 0,
) -> GenerationsAttemptApiResponse:
    """List attempt generation groups."""
    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        raise HTTPException(status_code=401, detail="Profile not found. Please sign in again.")

    if not has_permission(profile.role_permissions, ARTIFACT_TYPE, "generations"):
        raise HTTPException(status_code=403, detail="You don't have permission to view attempt generations.")

    session_ids = [session_id] if session_id else None

    async with pool.acquire() as conn:
        results = await search_groups(
            conn,
            session_ids=session_ids,
            name=search,
            date_from=date_from,
            date_to=date_to,
            artifact_type=ARTIFACT_TYPE,
            limit=page_limit,
            offset=page_offset,
        )

    items = [
        GenerationsAttemptListItem(
            group_id=r.id,
            session_id=r.session_id,
            group_name=r.name or None,
            created_at=r.created_at,
        )
        for r in results
    ]

    return GenerationsAttemptApiResponse(
        actor_name=profile.name,
        items=items,
        total_count=len(items),
    )
