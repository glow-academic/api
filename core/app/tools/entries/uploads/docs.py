"""Uploads entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.uploads.create import create_upload
from app.tools.entries.uploads.get import get_upload
from app.tools.entries.uploads.refresh import refresh_uploads_internal
from app.tools.entries.uploads.search import search_uploads


async def get_uploads_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the uploads entry."""
    mv_info = await get_mv_info(conn, "uploads_mv")
    entry_table = await get_table_info(conn, "uploads_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="uploads",
        type="entry",
        description=(
            "Base upload entries track file uploads with their metadata (path, mime type, size). "
            "Each upload records the session context and generation status. "
            "Reads are served from the uploads_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_upload,
                description=(
                    "Creates a new uploads entry recording file metadata "
                    "(path, mime type, size) within a session."
                ),
            ),
            get_operation_info(
                refresh_uploads_internal,
                description="Refreshes uploads_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_upload,
                description="Batch retrieves uploads entries by ID from uploads_mv.",
            ),
            get_operation_info(
                search_uploads,
                description="Filtered paginated search against uploads_mv.",
            ),
        ],
    )
