"""Practice refresh logic — debounced via MVRefresher (uses shared enqueue helper).

Permission-checks and enqueues practice_mv refresh via the shared queue helper.
The actual REFRESH MATERIALIZED VIEW runs out-of-band in the per-MV
background worker.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.refresh.queue import enqueue_refreshes
from app.infra.refresh.types import RefreshResponse

# Tags to invalidate — artifact cache + resource caches
_TAGS = ["practice", "artifacts"]

# Views refreshed by this endpoint
_VIEWS = ["practice_mv"]


async def refresh_practice_client(
    pool: asyncpg.Pool,
    redis: Redis | None,
    *,
    profile_id: UUID,
) -> RefreshResponse:
    """Practice refresh — permission-check + enqueue, no synchronous MV refresh."""
    return await enqueue_refreshes(
        pool, redis,
        profile_id=profile_id,
        artifact_type="practice",
        targets=_VIEWS,
        tags=_TAGS,
    )
