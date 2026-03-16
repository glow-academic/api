"""Documents SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.documents.get import get_documents
from app.tools.resources.documents.types import GetDocumentResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["document", "scenario"]

DRAFT_ARTIFACTS = ["chat", "scenario"]


async def search_documents(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    department_ids: list[UUID] | None = None,
    draft_id: UUID | None = None,
    suggest_source: str | None = None,
    exclude_ids: list[UUID] | None = None,
    file_ids: list[UUID] | None = None,
    text_ids: list[UUID] | None = None,
    image_ids: list[UUID] | None = None,
    template: bool | None = None,
    bypass_cache: bool = False,
    *,
    document: bool = False,
    scenario: bool = False,
) -> list[GetDocumentResponse]:
    """Search documents with optional artifact/draft filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {
        "document": document,
        "scenario": scenario,
    }

    tags = ["resources", "documents"]
    key = cache_key(
        "/v5/resources/documents/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "department_ids": [str(i) for i in (department_ids or [])],
            "draft_id": str(draft_id) if draft_id else None,
            "suggest_source": suggest_source,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "file_ids": sorted(str(i) for i in (file_ids or [])),
            "text_ids": sorted(str(i) for i in (text_ids or [])),
            "image_ids": sorted(str(i) for i in (image_ids or [])),
            "template": template,
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetDocumentResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    # Build extra conditions for document-specific filters
    extra_conditions: list[tuple[str, object]] = []
    # Active filter
    extra_conditions.append(("{alias}.active = ${idx}", True))
    # Department access: user can see if document has matching department OR has no departments
    if department_ids:
        extra_conditions.append(
            (
                "({alias}.department_ids && ${idx} OR COALESCE(array_length({alias}.department_ids, 1), 0) = 0)",
                department_ids,
            ),
        )
    if file_ids:
        extra_conditions.append(
            ("{alias}.file_id = ANY(${idx})", file_ids),
        )
    if text_ids:
        extra_conditions.append(
            ("{alias}.text_id = ANY(${idx})", text_ids),
        )
    if image_ids:
        extra_conditions.append(
            ("{alias}.image_ids && ${idx}", image_ids),
        )
    if template is not None:
        extra_conditions.append(
            ("{alias}.template = ${idx}", template),
        )

    ids = await search_resource_ids(
        conn,
        table="documents_resource",
        resource="documents",
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

    items = await get_documents(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
