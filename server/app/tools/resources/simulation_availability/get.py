"""Simulation Availability Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.simulation_availability.types import (
    GetSimulationAvailabilityResponse,
)
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_simulation_availability(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetSimulationAvailabilityResponse]:
    """Fetch simulation_availability_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "simulation_availability"]
    key = cache_key(
        "/v5/resources/simulation_availability/get",
        {"ids": [str(id) for id in ids]},
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetSimulationAvailabilityResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, simulation_id, time, type,
               created_at, updated_at, active, generated, mcp
        FROM simulation_availability_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
    """,
        ids,
    )

    items = [
        GetSimulationAvailabilityResponse(
            id=r["id"],
            simulation_id=r["simulation_id"],
            time=r["time"],
            type=r["type"],
            created_at=r["created_at"],
            updated_at=r["updated_at"],
            active=r["active"],
            generated=r["generated"],
            mcp=r["mcp"],
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
