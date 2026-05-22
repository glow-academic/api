"""Resolve common context — profile + tool graph + runs.

Central entry point for any artifact GET. Given a profile_id, resolves:
  1. ProfileIdentityContext (sequential — needed for settings_id + department_ids)
  2. In parallel: SettingsToolGraph + RunsContext

Composes existing infra functions — no raw SQL.
"""

from __future__ import annotations

import asyncio
import contextvars
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


# Request-scoped cache. Same request may resolve common context twice (the
# audit wrapper at top of the route + the inner *_impl function), with
# identical args. Memoize per (profile_id, group_id, bypass_cache) for the
# lifetime of the request — asyncio ContextVar isolates this per task tree.
# Saves ~12ms warm on every artifact GET that goes through the audit wrapper.
_request_cache: contextvars.ContextVar[
    "dict[tuple[UUID, UUID | None, bool], CommonContext] | None"
] = contextvars.ContextVar("common_ctx_request_cache", default=None)


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
    from app.infra.server_timing import timed

    # Request-scoped memoization: most requests resolve common context twice
    # (audit wrapper + runner) with identical args. Skip the second call.
    # Caller-provided `profile` bypasses the cache since it implies an
    # already-resolved context that may diverge from what's cached.
    cache_key = (profile_id, group_id, bypass_cache)
    cache = _request_cache.get()
    if profile is None and not bypass_cache and cache is not None:
        hit = cache.get(cache_key)
        if hit is not None:
            with timed("ctx_cached"):
                return hit

    # Step 1: profile (skip if pre-resolved)
    if profile is None:
        with timed("ctx_profile"):
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
    with timed("ctx_tools_runs"):
        tool_graph, runs = await asyncio.gather(
            resolve_tool_graph(pool, profile.settings_id, redis, bypass_cache)
            if profile.settings_id
            else _empty_tool_graph(),
            resolve_runs_context(pool, profile_id=profile_id, group_id=group_id),
        )

    result = CommonContext(
        profile=profile,
        tool_graph=tool_graph,
        runs=runs,
    )

    # Store in request-scoped cache for subsequent calls within this request.
    # First store creates the dict; later stores append.
    if not bypass_cache:
        if cache is None:
            cache = {}
            _request_cache.set(cache)
        cache[cache_key] = result

    return result


async def _empty_tool_graph() -> SettingsToolGraph:
    return SettingsToolGraph(tools=[])
