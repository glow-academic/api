"""Attempt watch — one-shot block-until-done for the tool layer.

The HTTP route ``GET /attempt/watch`` stays as live SSE for the browser.
This impl is its tool-layer sibling — same hub events, but returns a
single ``WatchApiResponse`` describing which runs finished and what
they produced.

Function name matches the ``{operation}_{artifact}_impl`` discovery
convention so ``(attempt, watch)`` auto-resolves to this callable
without needing an INFRA_OPS override.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra._watch import WatchApiResponse, watch_runs_impl
from app.infra.attempt.permissions import enforce_attempt_access_by_group
from app.infra.profile_identity_context import resolve_profile_identity_context


async def watch_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    group_id: UUID,
    run_id: UUID | None = None,
    wait_for_complete: bool = True,
    timeout_seconds: int = 120,
    **_kwargs,
) -> WatchApiResponse:
    """Watch a attempt-scoped run in ``group_id``."""
    # ── Ownership gate (R2, mirror of G3) ────────────────────────────────
    # ``group_id`` is caller-supplied; ``watch_runs_impl`` documents its
    # ``profile_id`` as "checked at route", but the route only authenticates —
    # so without this, any authenticated caller could watch another user's run
    # completion + the media it produced (read-side IDOR). The attempt group is
    # per-session-private, so resolve group → session → owner and apply the
    # shared attempt gate before subscribing to the victim's run events.
    requester = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    await enforce_attempt_access_by_group(
        pool, redis, group_id=group_id, requester=requester,
    )
    return await watch_runs_impl(
        pool,
        redis,
        artifact_type="attempt",
        group_id=group_id,
        run_id=run_id,
        wait_for_complete=wait_for_complete,
        timeout_seconds=timeout_seconds,
        profile_id=profile_id,
        session_id=session_id,
    )
