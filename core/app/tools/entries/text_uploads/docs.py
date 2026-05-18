"""Text uploads entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.text_uploads.create import create_text_upload
from app.tools.entries.text_uploads.get import get_text_upload
from app.tools.entries.text_uploads.refresh import refresh_text_uploads
from app.tools.entries.text_uploads.search import search_text_uploads


async def get_text_uploads_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the text_uploads entry."""
    mv_info = await get_mv_info(conn, "text_uploads_mv")
    entry_table = await get_table_info(conn, "text_uploads_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="text_uploads",
        type="entry",
        description=(
            "Text upload entries link text artifacts to upload artifacts via a session. "
            "Each row associates a text with an upload, recording when and how it was generated. "
            "Reads are served from the text_uploads_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_text_upload,
                description=(
                    "Creates a new text_uploads entry linking a text to an upload "
                    "within a session."
                ),
            ),
            get_operation_info(
                refresh_text_uploads,
                description="Refreshes text_uploads_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_text_upload,
                description="Batch retrieves text_uploads entries by ID from text_uploads_mv.",
            ),
            get_operation_info(
                search_text_uploads,
                description="Filtered paginated search against text_uploads_mv.",
            ),
        ],
    )
