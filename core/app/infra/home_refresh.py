"""Home refresh logic — debounced via MVRefresher (uses shared enqueue helper).

Permission-checks and enqueues home_mv refresh via the shared queue helper.
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
_TAGS = ["home", "artifacts"]

# Views refreshed by this endpoint
_VIEWS = ["home_mv"]


async def refresh_home_client(
    pool: asyncpg.Pool,
    redis: Redis | None,
    *,
    profile_id: UUID,
) -> RefreshResponse:
    """Home refresh — permission-check + enqueue, no synchronous MV refresh."""
    return await enqueue_refreshes(
        pool, redis,
        profile_id=profile_id,
        artifact_type="home",
        targets=_VIEWS,
        tags=_TAGS,
    )
