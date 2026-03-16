"""Documents CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.documents.get import get_documents
from app.tools.resources.documents.types import GetDocumentResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_document(
    conn: asyncpg.Connection,
    redis: Redis,
    id: UUID | None = None,
    name: str = "",
    description: str = "",
    mcp: bool = False,
    soft: bool = False,
    department_ids: list[UUID] | None = None,
    image_ids: list[UUID] | None = None,
    parameter_field_ids: list[UUID] | None = None,
) -> GetDocumentResponse:
    """Create a document resource (plain INSERT — no unique constraint)."""
    document_id = await conn.fetchval(
        """
        INSERT INTO documents_resource (id, name, description, active, mcp, generated, department_ids, image_ids, parameter_field_ids)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, $4, $6, $7, $8)
        RETURNING id
    """,
        name,
        description,
        not soft,
        mcp,
        id,
        department_ids or [],
        image_ids or [],
        parameter_field_ids or [],
    )

    await invalidate_tags(["resources", "documents"], redis=redis)
    items = await get_documents(conn, [document_id], redis, bypass_cache=True)
    return items[0]
