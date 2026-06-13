"""Test watch — one-shot block-until-done for the tool layer.

The HTTP route ``GET /test/watch`` stays as live SSE for the browser.
This impl is its tool-layer sibling — same hub events, but returns a
single ``WatchApiResponse`` describing which runs finished and what
they produced.

Function name matches the ``{operation}_{artifact}_impl`` discovery
convention so ``(test, watch)`` auto-resolves to this callable
without needing an INFRA_OPS override.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra._watch import WatchApiResponse, watch_runs_impl
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.test.permissions import enforce_test_access_by_group


async def watch_test_impl(
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
    """Watch a test-scoped run in ``group_id``."""
    # ── Ownership gate (G3) ──────────────────────────────────────────────
    # ``group_id`` is caller-supplied; ``watch_runs_impl`` documents its
    # ``profile_id`` as "checked at route", but the route does NOT gate it —
    # so without this, any authenticated caller could watch another user's
    # run completion + the media it produced (read-side IDOR). The test group
    # is per-session-private, so resolve group → session → owner and apply the
    # shared test gate before subscribing to the victim's run events.
    requester = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    await enforce_test_access_by_group(
        pool, redis, group_id=group_id, requester=requester,
    )
    return await watch_runs_impl(
        pool,
        redis,
        artifact_type="test",
        group_id=group_id,
        run_id=run_id,
        wait_for_complete=wait_for_complete,
        timeout_seconds=timeout_seconds,
        profile_id=profile_id,
        session_id=session_id,
    )
