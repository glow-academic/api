"""Temperature Levels SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.temperature_levels.get import get_temperature_levels
from app.tools.resources.temperature_levels.types import (
    GetTemperatureLevelResponse,
)
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["agent", "model"]


async def _search_temperature_level_ids(
    conn: asyncpg.Connection,
    *,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    artifact_filters: dict[str, bool] | None = None,
) -> list[UUID]:
    """Search temperature_levels_resource and return matching IDs.

    Temperature levels have a numeric column (temperature real) rather than
    a text name column, so we use a dedicated query instead of the generic
    search_resource_ids helper.
    """
    if limit_count <= 0:
        return []

    alias = "r"
    conditions: list[str] = []
    params: list[object] = []
    idx = 1

    # Search filter (cast temperature to text)
    if search:
        conditions.append(
            f"CAST({alias}.temperature AS text) LIKE '%' || ${idx} || '%'"
        )
        params.append(search)
        idx += 1

    # Exclude filter
    if exclude_ids:
        conditions.append(f"NOT ({alias}.id = ANY(${idx}))")
        params.append(exclude_ids)
        idx += 1

    # Artifact boolean filters
    if artifact_filters:
        for artifact, enabled in artifact_filters.items():
            if enabled:
                junction = f"{artifact}_temperature_levels_junction"
                conditions.append(
                    f"EXISTS (SELECT 1 FROM {junction} j WHERE j.temperature_levels_id = {alias}.id AND j.active = true)"
                )

    where = " AND ".join(conditions) if conditions else "TRUE"

    query = f"""
        SELECT {alias}.id
        FROM temperature_levels_resource {alias}
        WHERE {where}
        ORDER BY {alias}.temperature
        LIMIT ${idx} OFFSET ${idx + 1}
    """
    params.extend([limit_count, offset_count])

    rows = await conn.fetch(query, *params)
    return [row["id"] for row in rows]


async def search_temperature_levels(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    agent: bool = False,
    model: bool = False,
) -> list[GetTemperatureLevelResponse]:
    """Search temperature levels with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {"agent": agent, "model": model}

    tags = ["resources", "temperature_levels"]
    key = cache_key(
        "/v5/resources/temperature_levels/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetTemperatureLevelResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await _search_temperature_level_ids(
        conn,
        search=search,
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        artifact_filters=artifact_filters,
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_temperature_levels(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
