"""Videos SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.videos.get import get_videos
from app.tools.resources.videos.types import GetVideoResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["scenario"]


async def search_videos(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    upload_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    scenario: bool = False,
) -> list[GetVideoResponse]:
    """Search videos with optional artifact filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {"scenario": scenario}

    extra_conditions: list[tuple[str, object]] = []
    if upload_ids:
        extra_conditions.append(
            (
                "EXISTS (SELECT 1 FROM videos_videos_connection vvc "
                "JOIN videos_entry ve ON ve.id = vvc.video_id AND ve.active = true "
                "JOIN video_uploads_entry vue ON vue.video_id = ve.id AND vue.active = true "
                "WHERE vvc.video_id = {alias}.id AND vvc.active = true AND vue.upload_id = ANY(${idx}))",
                upload_ids,
            ),
        )

    tags = ["resources", "videos"]
    key = cache_key(
        "/v5/resources/videos/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "upload_ids": sorted(str(i) for i in (upload_ids or [])),
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetVideoResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    ids = await search_resource_ids(
        conn,
        table="videos_resource",
        resource="videos",
        search_column="name",
        search=search,
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        artifact_filters=artifact_filters,
        junction_artifacts=JUNCTION_ARTIFACTS,
        extra_conditions=extra_conditions if extra_conditions else None,
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_videos(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
