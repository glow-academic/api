"""File uploads entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.file_uploads.create import create_file_upload
from app.tools.entries.file_uploads.get import get_file_upload
from app.tools.entries.file_uploads.refresh import refresh_file_uploads
from app.tools.entries.file_uploads.search import search_file_uploads


async def get_file_uploads_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the file_uploads entry."""
    mv_info = await get_mv_info(conn, "file_uploads_mv")
    entry_table = await get_table_info(conn, "file_uploads_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="file_uploads",
        type="entry",
        description=(
            "File upload entries link file artifacts to upload artifacts via a session. "
            "Each row associates a file with an upload, recording when and how it was generated. "
            "Reads are served from the file_uploads_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_file_upload,
                description=(
                    "Creates a new file_uploads entry linking a file to an upload "
                    "within a session."
                ),
            ),
            get_operation_info(
                refresh_file_uploads,
                description="Refreshes file_uploads_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_file_upload,
                description="Batch retrieves file_uploads entries by ID from file_uploads_mv.",
            ),
            get_operation_info(
                search_file_uploads,
                description="Filtered paginated search against file_uploads_mv.",
            ),
        ],
    )
