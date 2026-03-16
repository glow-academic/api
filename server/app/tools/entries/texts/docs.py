"""Texts entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.texts.create import create_text
from app.tools.entries.texts.get import get_text
from app.tools.entries.texts.refresh import refresh_texts_internal
from app.tools.entries.texts.search import search_texts


async def get_texts_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the texts entry."""
    mv_info = await get_mv_info(conn, "texts_mv")
    entry_table = await get_table_info(conn, "texts_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="texts",
        type="entry",
        description=(
            "Texts entries represent text content generated or stored during sessions. "
            "Each texts entry is associated with a session and contains text data. "
            "Reads are served from the texts_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_text,
                description="Creates a new texts entry for a session.",
            ),
            get_operation_info(
                refresh_texts_internal,
                description="Refreshes texts_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_text,
                description="Batch retrieves texts entries by IDs from texts_mv.",
            ),
            get_operation_info(
                search_texts,
                description="Filtered paginated search against texts_mv.",
            ),
        ],
    )
