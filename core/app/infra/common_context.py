"""Resolve common context — profile resolution with request-scoped memoization.

Central entry point for any artifact GET. Resolves the
``ProfileIdentityContext`` and dedupes within a request via a ContextVar
cache. ``tool_graph`` and ``runs`` used to live here but moved to direct
callers in v1.0.48 — they were paid by every authed request even though
only a handful of consumers needed them (generation/prepare,
websocket_context, health/get, session/get).
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import (
    ProfileIdentityContext,
    resolve_profile_identity_context,
)


@dataclass(frozen=True)
class CommonContext:
    """Shared context for any artifact GET — just the profile."""

    profile: ProfileIdentityContext


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
    """Resolve profile identity, memoized within the request scope.

    Tool graph + runs were previously gathered in parallel here. They
    moved to direct callers (generation/prepare, websocket_context,
    health/get, session/get) — every authed request was paying 40ms+
    for resolutions the audit wrapper and ~28 endpoints never read.

    Returns None if profile not found.
    """
    from app.infra.server_timing import timed

    # Request-scoped memoization: audit wrapper + inner impl resolve the
    # same profile twice. Caller-provided `profile` bypasses (it implies
    # an already-resolved context that may diverge from what's cached).
    cache_key = (profile_id, group_id, bypass_cache)
    cache = _request_cache.get()
    if profile is None and not bypass_cache and cache is not None:
        hit = cache.get(cache_key)
        if hit is not None:
            with timed("ctx_cached"):
                return hit

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

    result = CommonContext(profile=profile)

    if not bypass_cache:
        if cache is None:
            cache = {}
            _request_cache.set(cache)
        cache[cache_key] = result

    return result
