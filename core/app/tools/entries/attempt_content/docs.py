"""Attempt content entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.attempt_content.create import create_attempt_content
from app.tools.entries.attempt_content.get import get_attempt_contents
from app.tools.entries.attempt_content.refresh import refresh_attempt_content
from app.tools.entries.attempt_content.search import search_attempt_contents


async def get_attempt_content_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the attempt_content entry."""
    mv_info = await get_mv_info(conn, "attempt_content_mv")
    entry_table = await get_table_info(conn, "attempt_content_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="attempt_content",
        type="entry",
        description=(
            "Message content records storing the actual text content of messages "
            "along with the persona that generated the content. "
            "Each content entry references a message and a persona. "
            "Reads are served from the attempt_content_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_attempt_content,
                description="Creates a new attempt_content entry for a message.",
            ),
            get_operation_info(
                refresh_attempt_content,
                description="Refreshes attempt_content_mv concurrently.",
            ),
            get_operation_info(
                get_attempt_contents,
                description="Batch retrieves contents by IDs from attempt_content_mv.",
            ),
            get_operation_info(
                search_attempt_contents,
                description="Filtered paginated search against attempt_content_mv.",
            ),
        ],
    )
