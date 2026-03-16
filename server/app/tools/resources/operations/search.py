"""Operations SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.operations.get import get_operations
from app.tools.resources.operations.types import GetOperationResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["tool"]


async def search_operations(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    tool: bool = False,
) -> list[GetOperationResponse]:
    """Search operations with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {
        "tool": tool,
    }

    tags = ["resources", "operations"]
    key = cache_key(
        "/v5/resources/operations/search",
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
                GetOperationResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    conditions = ["r.active = true"]
    params: list[object] = []
    idx = 1

    if search:
        conditions.append(f"LOWER(r.operation::text) LIKE '%' || LOWER(${idx}) || '%'")
        params.append(search)
        idx += 1

    if exclude_ids:
        conditions.append(f"NOT (r.id = ANY(${idx}))")
        params.append(exclude_ids)
        idx += 1

    if tool:
        conditions.append(
            "EXISTS (SELECT 1 FROM tool_operations_junction j "
            "WHERE j.operations_id = r.id AND j.active = true)"
        )

    rows = await conn.fetch(
        f"""
        SELECT r.id
        FROM operations_resource r
        WHERE {" AND ".join(conditions)}
        ORDER BY r.operation
        LIMIT ${idx} OFFSET ${idx + 1}
        """,
        *params,
        limit_count,
        offset_count,
    )
    ids = [row["id"] for row in rows]

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_operations(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
