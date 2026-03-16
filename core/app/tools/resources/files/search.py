"""Files SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.files.get import get_files
from app.tools.resources.files.types import GetFileResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["document"]


async def search_files(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    document: bool = False,
) -> list[GetFileResponse]:
    """Search files with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {
        "document": document,
    }

    tags = ["resources", "files"]
    key = cache_key(
        "/v5/resources/files/search",
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
                GetFileResponse.model_validate(item) for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="files_resource",
        resource="files",
        search_column=None,
        search=None,
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        artifact_filters=artifact_filters,
        junction_artifacts=JUNCTION_ARTIFACTS,
        order_column="created_at DESC",
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_files(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
