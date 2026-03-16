"""Scenario Time Limits Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.scenario_time_limits.types import (
    GetScenarioTimeLimitResponse,
)
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_scenario_time_limits(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetScenarioTimeLimitResponse]:
    """Fetch scenario_time_limits_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "scenario_time_limits"]
    key = cache_key(
        "/v5/resources/scenario_time_limits/get", {"ids": [str(id) for id in ids]}
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetScenarioTimeLimitResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, scenario_id, time_limit_seconds, negative,
               created_at, active, mcp, generated
        FROM scenario_time_limits_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
    """,
        ids,
    )

    items = [
        GetScenarioTimeLimitResponse(
            id=r["id"],
            scenario_id=r["scenario_id"],
            time_limit_seconds=r["time_limit_seconds"],
            negative=r["negative"],
            created_at=r["created_at"],
            active=r["active"],
            mcp=r["mcp"],
            generated=r["generated"],
        )
        for r in rows
    ]

    if not bypass_cache:
        await set_cached(
            key,
            {"items": [i.model_dump(mode="json") for i in items]},
            60,
            tags,
            redis=redis,
        )
    return items
