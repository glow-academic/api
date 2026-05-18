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
) -> CommonContext | None:
    """Resolve common context for any artifact GET.

    Steps:
      1. resolve_profile_identity_context — sequential (need settings_id for step 2)
         Skipped if ``profile`` is already provided (pre-resolved at boundary).
      2. In parallel:
         a. resolve_tool_graph(settings_id)
         b. resolve_runs_context(profile_id, group_id)

    Callers are responsible for resolving ``group_id`` themselves — either
    via ``resolve_group`` (attempt/test context) or ``resolve_group_impl``
    (fresh per-artifact group). Identity no longer side-effects a group_id.

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
        )
    if profile is None:
        return None

    # Step 2: tool graph + runs in parallel
    tool_graph, runs = await asyncio.gather(
        resolve_tool_graph(pool, profile.settings_id, redis, bypass_cache)
        if profile.settings_id
        else _empty_tool_graph(),
        resolve_runs_context(pool, profile_id=profile_id, group_id=group_id),
    )

    return CommonContext(
        profile=profile,
        tool_graph=tool_graph,
        runs=runs,
    )


async def _empty_tool_graph() -> SettingsToolGraph:
    return SettingsToolGraph(tools=[])
