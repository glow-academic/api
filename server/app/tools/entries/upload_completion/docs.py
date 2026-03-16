"""Upload completion entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.upload_completion.create import (
    create_upload_completion,
)
from app.tools.entries.upload_completion.get import get_upload_completion
from app.tools.entries.upload_completion.refresh import (
    refresh_upload_completion,
)
from app.tools.entries.upload_completion.search import (
    search_upload_completions,
)


async def get_upload_completion_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the upload_completion entry."""
    mv_info = await get_mv_info(conn, "upload_completion_mv")
    entry_table = await get_table_info(conn, "upload_completion_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="upload_completion",
        type="entry",
        description=(
            "Upload completion entries track AI-generated completions for uploads. "
            "Each row links an upload to a completion artifact within a session. "
            "Reads are served from the upload_completion_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_upload_completion,
                description=(
                    "Creates a new upload_completion entry linking an upload "
                    "to a completion within a session."
                ),
            ),
            get_operation_info(
                refresh_upload_completion,
                description="Refreshes upload_completion_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_upload_completion,
                description="Batch retrieves upload_completion entries by ID from upload_completion_mv.",
            ),
            get_operation_info(
                search_upload_completions,
                description="Filtered paginated search against upload_completion_mv.",
            ),
        ],
    )
