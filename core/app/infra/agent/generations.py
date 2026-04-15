"""Agent generations logic — list generation groups for agents.

Composes existing black-box tools:
  1. resolve_profile_identity_context -- profile (role, permissions)
  2. search_groups -- core MV search with artifact_type="agent" filter
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.agent.types import (
    GenerationsAgentApiResponse,
    GenerationsAgentListItem,
)
from app.tools.entries.groups.search import search_groups

ARTIFACT_TYPE = "agent"


async def generations_agent_impl(
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
) -> GenerationsAgentApiResponse:
    """List agent generation groups.

    Flow:
      1. resolve_profile_identity_context -> role, permissions
      2. Permission check -- agent:generations
      3. search_groups with artifact_type="agent"
    """
    # -- Step 1: Profile context ------------------------------------------------

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Permission check -----------------------------------------------

    if not has_permission(profile.role_permissions, ARTIFACT_TYPE, "generations"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to view agent generations.",
        )

    # -- Step 3: Search groups --------------------------------------------------

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

    # -- Step 4: Build response -------------------------------------------------

    items = [
        GenerationsAgentListItem(
            group_id=r.id,
            session_id=r.session_id,
            group_name=r.name or None,
            created_at=r.created_at,
        )
        for r in results
    ]

    return GenerationsAgentApiResponse(
        actor_name=profile.name,
        items=items,
        total_count=len(items),
    )
