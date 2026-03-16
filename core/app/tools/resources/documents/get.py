"""Documents Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.documents.types import GetDocumentResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_documents(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetDocumentResponse]:
    """Fetch documents_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "documents"]
    key = cache_key("/v5/resources/documents/get", {"ids": [str(id) for id in ids]})

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetDocumentResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, name, description, department_ids, file_id, text_id, image_ids,
               template, parameter_field_ids, created_at, active,
               generated, mcp
        FROM documents_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
    """,
        ids,
    )

    items = [
        GetDocumentResponse(
            id=r["id"],
            name=r["name"],
            description=r["description"],
            department_ids=r["department_ids"] or [],
            file_id=r["file_id"],
            text_id=r["text_id"],
            image_ids=r["image_ids"] or [],
            template=r["template"],
            parameter_field_ids=r["parameter_field_ids"] or [],
            created_at=r["created_at"],
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
