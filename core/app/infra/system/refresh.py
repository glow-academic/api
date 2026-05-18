"""System refresh — Phase A stub.

Invalidates system-scope cache tags so the next read goes back to the DB.
Per Phase A, this does NOT refresh any materialized views — view-level MV
refresh is added in Phase B per view (activity, pricing, group, health,
session). Mirrors the canonical refresh impl shape (see
`app.infra.attempt.refresh.refresh_attempt_impl`).
"""

from __future__ import annotations

import time
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.refresh.types import RefreshResponse
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.logging.db_logger import get_logger

ARTIFACT_TYPE = "system"

# Tags invalidated by this endpoint — union of tags used by every
# system-scope GET endpoint (verified against
# core/app/routes/system/{activity,pricing,group,health,session}/*.py and
# infra/system/{page_context,generations}.py). Touching this list keeps
# the page caches honest across the entire analytics surface.
_TAGS = [
    "artifacts",
    "activity",
    "pricing",
    "group",
    "health",
    "session",
    "system",
    "context",
    "list",
    "detail",
    "problems",
]

logger = get_logger(__name__)


async def refresh_system_impl(
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
    """System refresh — invalidate cache tags only (no MV refresh in Phase A)."""
    _ = (pool, profile_id, session_id, soft, accept)  # unused in Phase A stub
    effective_op_key = operation_key or idempotency_key

    t0 = time.monotonic()
    if redis is not None:
        await invalidate_tags(_TAGS, redis=redis)
    duration_ms = int((time.monotonic() - t0) * 1000)
    logger.info(
        f"[refresh-system] invalidated {len(_TAGS)} tags in {duration_ms}ms",
    )

    return RefreshResponse(
        success=True,
        refreshed_views=[],
        invalidated_tags=_TAGS,
        idempotency_key=effective_op_key,
    )
