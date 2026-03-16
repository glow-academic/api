"""Thresholds SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.thresholds.get import get_thresholds
from app.tools.resources.thresholds.types import GetThresholdResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["setting"]


async def search_thresholds(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    draft_id: UUID | None = None,
    suggest_source: str | None = None,
    exclude_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    setting: bool = False,
) -> list[GetThresholdResponse]:
    """Search thresholds with optional artifact filters.

    Note: thresholds_resource has no text columns (only integer value),
    so this uses a direct query rather than search_resource_ids.
    """
    if limit_count <= 0:
        return []

    artifact_filters = {
        "setting": setting,
    }

    tags = ["resources", "thresholds"]
    key = cache_key(
        "/v5/resources/thresholds/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "draft_id": str(draft_id) if draft_id else None,
            "suggest_source": suggest_source,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetThresholdResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    # Build dynamic WHERE for ID search
    # thresholds has no text columns, so we use a direct query
    alias = "r"
    conditions: list[str] = [f"{alias}.active = true"]
    params: list[object] = []
    idx = 1

    # Exclude filter
    if exclude_ids:
        conditions.append(f"NOT ({alias}.id = ANY(${idx}))")
        params.append(exclude_ids)
        idx += 1

    # Artifact junction filters
    if artifact_filters.get("setting"):
        conditions.append(
            f"EXISTS (SELECT 1 FROM setting_thresholds_junction j WHERE j.thresholds_id = {alias}.id AND j.active = true)"
        )

    where = " AND ".join(conditions)
    query = f"""
        SELECT {alias}.id
        FROM thresholds_resource {alias}
        WHERE {where}
        ORDER BY {alias}.value
        LIMIT ${idx} OFFSET ${idx + 1}
    """
    params.extend([limit_count, offset_count])

    rows = await conn.fetch(query, *params)
    ids = [row["id"] for row in rows]

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_thresholds(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
