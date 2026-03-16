"""Texts resource documentation."""

import asyncpg

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.resources.texts.create import create_text
from app.tools.resources.texts.get import get_texts
from app.tools.resources.texts.search import search_texts


async def get_texts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the texts resource."""
    resource_table = await get_table_info(conn, "texts_resource")
    tables = [t for t in [resource_table] if t is not None]

    return DocsResponse(
        name="texts",
        type="resource",
        description="Text content blocks for document resources.",
        tables=tables,
        operations=[
            get_operation_info(
                create_text,
                description="Creates a new texts resource.",
            ),
            get_operation_info(
                get_texts,
                description="Batch retrieves texts by IDs.",
            ),
            get_operation_info(
                search_texts,
                description="Filtered paginated search returning matching texts.",
            ),
        ],
    )
