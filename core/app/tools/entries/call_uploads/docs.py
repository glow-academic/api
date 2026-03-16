"""Call uploads entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.call_uploads.create import create_call_upload
from app.tools.entries.call_uploads.get import get_call_upload
from app.tools.entries.call_uploads.refresh import refresh_call_uploads
from app.tools.entries.call_uploads.search import search_call_uploads


async def get_call_uploads_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the call_uploads entry."""
    mv_info = await get_mv_info(conn, "call_uploads_mv")
    entry_table = await get_table_info(conn, "call_uploads_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="call_uploads",
        type="entry",
        description=(
            "Call upload entries link call artifacts to upload artifacts via a session. "
            "Each row associates a call with an upload, recording when and how it was generated. "
            "Reads are served from the call_uploads_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_call_upload,
                description=(
                    "Creates a new call_uploads entry linking a call to an upload "
                    "within a session."
                ),
            ),
            get_operation_info(
                refresh_call_uploads,
                description="Refreshes call_uploads_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_call_upload,
                description="Batch retrieves call_uploads entries by ID from call_uploads_mv.",
            ),
            get_operation_info(
                search_call_uploads,
                description="Filtered paginated search against call_uploads_mv.",
            ),
        ],
    )
