"""Message uploads entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.message_uploads.create import create_message_upload
from app.tools.entries.message_uploads.get import get_message_upload
from app.tools.entries.message_uploads.refresh import refresh_message_uploads
from app.tools.entries.message_uploads.search import search_message_uploads


async def get_message_uploads_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the message_uploads entry."""
    mv_info = await get_mv_info(conn, "message_uploads_mv")
    entry_table = await get_table_info(conn, "message_uploads_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="message_uploads",
        type="entry",
        description=(
            "Message upload entries link message artifacts to upload artifacts via a session. "
            "Each row associates a message with an upload, recording when and how it was generated. "
            "Reads are served from the message_uploads_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_message_upload,
                description=(
                    "Creates a new message_uploads entry linking a message to an upload "
                    "within a session."
                ),
            ),
            get_operation_info(
                refresh_message_uploads,
                description="Refreshes message_uploads_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_message_upload,
                description="Batch retrieves message_uploads entries by ID from message_uploads_mv.",
            ),
            get_operation_info(
                search_message_uploads,
                description="Filtered paginated search against message_uploads_mv.",
            ),
        ],
    )
