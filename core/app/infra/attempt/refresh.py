"""Attempt refresh — debounced via MVRefresher (uses shared enqueue helper)."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.refresh.queue import enqueue_refreshes
from app.infra.refresh.types import RefreshResponse

ARTIFACT_TYPE = "attempt"

# Tags to invalidate — artifact cache + resource caches
_TAGS = ["attempt", "artifacts"]

# Views refreshed by this endpoint
ALL_TARGETS = ["attempt_mv", "runs_mv", "messages_mv", "calls_mv"]


async def refresh_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis | None,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    targets: list[str] | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    operation_key: UUID | None = None,
    **_kwargs,
) -> RefreshResponse:
    """Attempt refresh — permission-check + enqueue, no synchronous MV refresh.

    Honors a caller-supplied ``targets`` list (mirrors ``refresh_chat_impl``).
    Every mutate in the attempt cluster (message/grade/feedback/hint/strength/
    improvement/analysis/response/chat_*) passes the specific ``*_mv`` it
    actually invalidated. Previously this argument was swallowed by ``**_kwargs``
    and only ``ALL_TARGETS`` was ever enqueued, so the per-feature MVs those
    mutates write (e.g. ``attempt_grade_mv``, ``attempt_message_tree_mv``)
    never had their refresh enqueued — and since the MVRefresher worker only
    runs a target when something enqueues it, those reads stayed stale until a
    manual full refresh. Fall back to ``ALL_TARGETS`` when no targets given.
    """
    effective_targets = targets or ALL_TARGETS
    effective_op_key = operation_key or idempotency_key
    return await enqueue_refreshes(
        pool, redis,
        profile_id=profile_id,
        session_id=session_id,
        artifact_type=ARTIFACT_TYPE,
        targets=effective_targets,
        idempotency_key=effective_op_key,
        tags=_TAGS,
        soft=soft,
        accept=accept,
    )
