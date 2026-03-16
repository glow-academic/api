"""Rubric drafts list logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (profiles_id)
  2. search_rubric_drafts — declarative filter by profile ownership
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.types import ArtifactContext
from app.tools.entries.rubric_drafts.search import search_rubric_drafts


async def list_rubric_drafts_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """List rubric drafts owned by the current profile.

    Flow:
      1. resolve_profile_identity_context → profiles_id
      2. search_rubric_drafts(profile_ids=[profiles_id]) → entries
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

    # ── Step 2: Search drafts by ownership ─────────────────────────────

    async with pool.acquire() as conn:
        drafts = await search_rubric_drafts(
            conn,
            profile_ids=[profile.profiles_id],
        )

    # ── Step 3: Return canonical ArtifactContext ───────────────────────

    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=profile.group_id or UUID(int=0),
        draft_version=None,
        resources={},
        entries={"drafts": drafts},
    )
