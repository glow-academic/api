"""Request Limits CREATE — reusable data-access layer."""

from datetime import timedelta
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.request_limits.get import get_request_limits
from app.tools.resources.request_limits.types import GetRequestLimitResponse
from app.utils.cache.invalidate_tags import invalidate_tags

# Map common interval strings to timedelta
_INTERVAL_MAP = {
    "1 day": timedelta(days=1),
    "1 hour": timedelta(hours=1),
    "30 minutes": timedelta(minutes=30),
    "7 days": timedelta(days=7),
    "1 month": timedelta(days=30),
}


async def create_request_limit(
    conn: asyncpg.Connection,
    limit: int,
    redis: Redis,
    id: UUID | None = None,
    interval: str = "1 day",
    mcp: bool = False,
    soft: bool = False,
) -> GetRequestLimitResponse:
    """Create a request_limit resource (plain INSERT — no unique constraint)."""
    interval_td = _INTERVAL_MAP.get(interval, timedelta(days=1))
    request_limit_id = await conn.fetchval(
        """
        INSERT INTO request_limits_resource (id, "limit", "interval", active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, $4)
        RETURNING id
        """,
        limit,
        interval_td,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "request_limits"], redis=redis)
    items = await get_request_limits(conn, [request_limit_id], redis, bypass_cache=True)
    return items[0]
