"""Pricing refresh — debounced via MVRefresher (uses shared enqueue helper)."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.refresh.queue import enqueue_refreshes
from app.infra.refresh.types import RefreshResponse

ARTIFACT_TYPE = "pricing"

# Tags to invalidate — artifact cache + resource caches
_TAGS = ["pricing", "artifacts"]

# Views refreshed by this endpoint
ALL_TARGETS = ["run_pricing_mv"]


async def refresh_pricing_impl(
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
    """Pricing refresh — permission-check + enqueue, no synchronous MV refresh."""
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
