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

# Includes the GLOBAL ``home``/``practice`` tags. A group is the backing
# entity for a simulation, and group renames (``title_group_impl`` →
# ``create_group_name`` → ``groups_mv``/``group_names_mv``) change the title
# the home/practice cards render per-simulation. Those reads register under
# ``["home"/"practice", "get"]`` + a per-profile tag and carry NO
# ``groups``/``artifacts`` tag, so without busting the global
# ``home``/``practice`` tags here a rename leaves stale card names across every
# student for the full 300s TTL (C5). Mirrors ``simulation/refresh._TAGS``,
# which the rename path does NOT flow through (it routes via this shared group
# refresh instead).
_TAGS = ["groups", "artifacts", "home", "practice"]
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
