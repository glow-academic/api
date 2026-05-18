"""Activity refresh — debounced via MVRefresher (uses shared enqueue helper)."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.refresh.queue import enqueue_refreshes
from app.infra.refresh.types import RefreshResponse

ARTIFACT_TYPE = "activity"

# Tags to invalidate — artifact cache + resource caches
_TAGS = ["activity", "artifacts"]

# Views read by the Activity page. The top cards use sessions/activity/logins/
# problems/grants/emulations; the history table joins sessions -> groups -> runs
# and computes cost from run pricing.
ALL_TARGETS = [
    "sessions_mv",
    "activity_mv",
    "logins_mv",
    "problems_mv",
    "grants_mv",
    "emulations_mv",
    "groups_mv",
    "runs_mv",
    "tokens_mv",
    "run_pricing_mv",
]


async def refresh_activity_impl(
    pool: asyncpg.Pool,
    redis: Redis | None,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    operation_key: UUID | None = None,
    **_kwargs: object,
) -> RefreshResponse:
    """Activity refresh — permission-check + enqueue, no synchronous MV refresh."""
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
