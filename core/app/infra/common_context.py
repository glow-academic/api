"""Resolve common context — profile + tool graph + runs.

Central entry point for any artifact GET. Given a profile_id, resolves:
  1. ProfileIdentityContext (sequential — needed for settings_id + department_ids)
  2. In parallel: SettingsToolGraph + RunsContext

Composes existing infra functions — no raw SQL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import (
    ProfileIdentityContext,
    resolve_profile_identity_context,
)
from app.infra.runs_context import RunsContext, resolve_runs_context
from app.infra.tool_graph import SettingsToolGraph, resolve_tool_graph


@dataclass(frozen=True)
class CommonContext:
    """Shared context for any artifact GET — profile, tools, and runs."""

    profile: ProfileIdentityContext
    tool_graph: SettingsToolGraph
    runs: RunsContext


async def resolve_common_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    profile: ProfileIdentityContext | None = None,
    session_id: UUID | None = None,
    group_id: UUID | None = None,
    bypass_cache: bool = False,
    # Group resolution hints — threaded to resolve_profile_identity_context
    draft_id: UUID | None = None,
    attempt_id: UUID | None = None,
    test_id: UUID | None = None,
    artifact_type: str | None = None,
) -> CommonContext | None:
    """Resolve common context for any artifact GET.

    Each parallel branch acquires its own connection from the pool.

    Steps:
      1. resolve_profile_identity_context — sequential (need settings_id for step 2)
         Skipped if ``profile`` is already provided (pre-resolved at boundary).
         When draft_id/artifact_type are provided, also resolves group_id.
      2. In parallel:
         a. resolve_tool_graph(settings_id)
         b. resolve_runs_context(profile_id, group_id)

    Returns None if profile not found.
    """
    # Step 1: profile (skip if pre-resolved)
    if profile is None:
        profile = await resolve_profile_identity_context(
            pool,
            profile_id,
            redis,
            bypass_cache,
            session_id=session_id,
            draft_id=draft_id,
            attempt_id=attempt_id,
            test_id=test_id,
            artifact_type=artifact_type,
        )
    if profile is None:
        return None

    # Use profile-resolved group_id if none was explicitly provided
    effective_group_id = group_id or profile.group_id

    # Step 2: tool graph + runs in parallel
    tool_graph, runs = await asyncio.gather(
        resolve_tool_graph(pool, profile.settings_id, redis, bypass_cache)
        if profile.settings_id
        else _empty_tool_graph(),
        resolve_runs_context(pool, profile_id=profile_id, group_id=effective_group_id),
    )

    return CommonContext(
        profile=profile,
        tool_graph=tool_graph,
        runs=runs,
    )


async def _empty_tool_graph() -> SettingsToolGraph:
    return SettingsToolGraph(tools=[])
