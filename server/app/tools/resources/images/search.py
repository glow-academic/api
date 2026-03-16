"""Images SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.images.get import get_images
from app.tools.resources.images.types import GetImageResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = [
    "document",
    "scenario",
]

DRAFT_ARTIFACTS = [
    "chat",
    "document",
    "scenario",
]


async def search_images(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    draft_id: UUID | None = None,
    suggest_source: str | None = None,
    exclude_ids: list[UUID] | None = None,
    upload_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    document: bool = False,
    scenario: bool = False,
) -> list[GetImageResponse]:
    """Search images with optional artifact/draft filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {
        "document": document,
        "scenario": scenario,
    }

    tags = ["resources", "images"]
    key = cache_key(
        "/v5/resources/images/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "draft_id": str(draft_id) if draft_id else None,
            "suggest_source": suggest_source,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "upload_ids": sorted(str(i) for i in (upload_ids or [])),
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetImageResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    # Build extra conditions for image-specific filters
    extra_conditions: list[tuple[str, object]] = []
    extra_conditions.append(("{alias}.active = ${idx}", True))
    if upload_ids:
        extra_conditions.append(
            (
                "EXISTS (SELECT 1 FROM images_images_connection iic "
                "JOIN images_entry ie ON ie.id = iic.image_id AND ie.active = true "
                "JOIN image_uploads_entry iue ON iue.image_id = ie.id AND iue.active = true "
                "WHERE iic.image_id = {alias}.id AND iic.active = true AND iue.upload_id = ANY(${idx}))",
                upload_ids,
            ),
        )

    ids = await search_resource_ids(
        conn,
        table="images_resource",
        resource="images",
        search_column="name",
        search=search,
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        draft_id=draft_id,
        suggest_source=suggest_source,
        artifact_filters=artifact_filters,
        junction_artifacts=JUNCTION_ARTIFACTS,
        draft_artifacts=DRAFT_ARTIFACTS,
        extra_conditions=extra_conditions if extra_conditions else None,
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_images(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
