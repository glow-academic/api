"""Setting drafts list logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile auth gate + session
  2. search_setting_drafts — declarative filter by session
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.types import ArtifactContext
from app.tools.entries.setting_drafts.search import search_setting_drafts


async def list_setting_drafts_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """List setting drafts for the caller's current session.

    Flow:
      1. resolve_profile_identity_context → auth + session_id
      2. search_setting_drafts(session_ids=[session_id]) → entries
      3. Return ArtifactContext(resources={}, entries={"drafts": [...]})
    """
    from fastapi import HTTPException

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, bypass_cache=bypass_cache
    )

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Search drafts by session ───────────────────────────────

    async with pool.acquire() as conn:
        drafts = await search_setting_drafts(
            conn,
            session_ids=[profile.session_id] if profile.session_id else None,
        )

    # ── Step 3: Return canonical ArtifactContext ───────────────────────

    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=UUID(int=0),
        resources={},
        entries={"drafts": drafts},
    )
