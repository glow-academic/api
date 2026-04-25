"""Reports refresh — debounced via MVRefresher (uses shared enqueue helper).

No dedicated entry refresh tools — permission check + cache invalidation only.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.refresh.queue import enqueue_refreshes
from app.infra.refresh.types import RefreshResponse

ARTIFACT_TYPE = "reports"

# Tags to invalidate — artifact cache + resource caches
_TAGS = ["reports", "artifacts"]

# No dedicated entry MVs to refresh
ALL_TARGETS: list[str] = []


async def refresh_reports_impl(
    pool: asyncpg.Pool,
    redis: Redis | None,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    operation_key: UUID | None = None,
    **_kwargs,
) -> RefreshResponse:
    """Reports refresh — permission-check + enqueue (no MVs)."""
    effective_op_key = operation_key or idempotency_key
    return await enqueue_refreshes(
        pool, redis,
        profile_id=profile_id,
        session_id=session_id,
        artifact_type=ARTIFACT_TYPE,
        targets=ALL_TARGETS,
        idempotency_key=effective_op_key,
        tags=_TAGS,
        soft=soft,
        accept=accept,
    )
