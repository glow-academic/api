"""Group refresh — debounced via MVRefresher (uses shared enqueue helper).

Pre-v2.15.19 this synchronously fired REFRESH MATERIALIZED VIEW CONCURRENTLY
group_names_mv + groups_mv on every group create/name (resolve.py:227).
With many concurrent group endpoints per page load, refreshes serialized
on the per-MV CONCURRENTLY lock and stalled the user response.

Now this just delegates to the shared `enqueue_refreshes` helper which
permission-checks, audits via create_refresh, and enqueues O(1) in Redis.
The actual REFRESH MATERIALIZED VIEW runs in the background per-MV worker
(app/infra/refresh/scheduler.py:MVRefresher).
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.refresh.queue import enqueue_refreshes
from app.infra.refresh.types import RefreshResponse

_TAGS = ["groups", "artifacts"]
_VIEWS = ["groups_mv", "group_names_mv"]


async def refresh_group_impl(
    pool: asyncpg.Pool,
    redis: Redis | None,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **_kwargs,
) -> RefreshResponse:
    """Group refresh — permission-check + enqueue, no synchronous MV refresh."""
    return await enqueue_refreshes(
        pool, redis,
        profile_id=profile_id,
        session_id=session_id,
        artifact_type="group",
        targets=_VIEWS,
        idempotency_key=idempotency_key,
        tags=_TAGS,
        soft=soft,
        accept=accept,
    )
