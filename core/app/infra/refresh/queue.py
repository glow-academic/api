"""Shared enqueue helper for artifact-level refresh orchestrators.

Every artifact's `app/infra/{artifact}/refresh.py` was previously calling
`_execute_refreshes(...)` which fanned out per-target REFRESH MATERIALIZED
VIEW CONCURRENTLY calls synchronously, holding the user response while the
DB-side MV lock serialized them.

This helper replaces that path. It:
  1. Permission-checks via resolve_profile_identity_context (delegates 401)
  2. Writes append-only audit rows to refreshes_entry via the canonical
     `tools.entries.refreshes.create_refresh` primitive (when session_id
     is supplied)
  3. Enqueues O(1) Redis pending flags via mv_refresh_queue.enqueue_pending
  4. Returns a RefreshResponse immediately

The actual REFRESH MATERIALIZED VIEW runs out-of-band in the per-MV
background worker (app/infra/refresh/scheduler.py:MVRefresher) which
debounces concurrent enqueues into one refresh per interval and serializes
across replicas via a Redis SET NX EX lock.

Cache invalidation moves with the refresh — each per-target primitive in
`app/tools/entries/{target}/refresh.py` is responsible for its own
invalidate_tags call.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.refresh.types import RefreshResponse
from app.tools.entries.refreshes.create import create_refresh
from app.utils.cache.mv_refresh_queue import enqueue_pending


async def enqueue_refreshes(
    pool: asyncpg.Pool,
    redis: Redis | None,
    *,
    profile_id: UUID,
    artifact_type: str,
    targets: list[str],
    session_id: UUID | None = None,
    idempotency_key: UUID | None = None,
    tags: list[str] | None = None,
    soft: bool = False,
    accept: bool | None = None,
) -> RefreshResponse:
    """Common enqueue path used by every artifact's refresh impl.

    soft / accept / idempotency_key preserve the persona-style ack lifecycle:
      - soft=True              → record audit only, do not enqueue Redis
      - accept=True + key set  → enqueue (executes "the pending refresh")
      - accept=False + key set → no-op
      - default                → record audit + enqueue
    """
    # Permission check — same as the previous synchronous orchestrators.
    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    op_key = idempotency_key or uuid4()
    response_tags = tags or []

    # Ack-flow short-circuit: explicit reject is a no-op (no audit, no enqueue).
    if accept is False and idempotency_key is not None:
        return RefreshResponse(
            success=True,
            refreshed_views=[],
            invalidated_tags=[],
            idempotency_key=op_key,
        )

    # 1. Append-only audit. Skipped when there's no session_id (HTTP-only
    # codepaths without a tied session); the worker doesn't need the rows
    # since pending state lives entirely in Redis.
    if session_id is not None:
        async with pool.acquire() as conn:
            for target in targets:
                await create_refresh(
                    conn,
                    operation_key=op_key,
                    artifact_type=artifact_type,
                    target=target,
                    session_id=session_id,
                )

    # 2. Synchronous tag invalidation — busts big-cache (L3) entries
    # immediately so the user's next read sees their write. Runs even in
    # soft mode: soft means "don't run the MV refresh yet" but the data
    # has already changed and stale cache entries must go. The MV refresh
    # itself is async in the worker, but cache correctness can't wait.
    if redis is not None and response_tags:
        from app.utils.cache.invalidate_tags import invalidate_tags
        await invalidate_tags(response_tags, redis=redis)

    # 3. soft mode = "record intent without enqueue" — caller will ack later
    # to actually run the MV refresh. We've already invalidated cache above,
    # so reads stay correct in the meantime (they'll cache-miss and rebuild
    # from the new data).
    if soft:
        return RefreshResponse(
            success=True,
            refreshed_views=[],
            invalidated_tags=response_tags,
            idempotency_key=op_key,
        )

    # 4. O(1) Redis enqueue — wakes the per-MV worker.
    if redis is not None:
        for target in targets:
            await enqueue_pending(redis, target)

    return RefreshResponse(
        success=True,
        refreshed_views=targets,
        invalidated_tags=response_tags,
        idempotency_key=op_key,
    )
