"""Attempt archive entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.attempt_archive.create import create_attempt_archive
from app.tools.entries.attempt_archive.get import get_attempt_archives
from app.tools.entries.attempt_archive.refresh import refresh_attempt_archive
from app.tools.entries.attempt_archive.search import search_attempt_archives


async def get_attempt_archive_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the attempt_archive entry."""
    mv_info = await get_mv_info(conn, "attempt_archive_mv")
    entry_table = await get_table_info(conn, "attempt_archive_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="attempt_archive",
        type="entry",
        description=(
            "Archive state records tracking whether an attempt is archived. "
            "Each record references an attempt and includes an archived boolean flag. "
            "Reads are served from the attempt_archive_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_attempt_archive,
                description="Creates a new attempt_archive entry for an attempt.",
            ),
            get_operation_info(
                refresh_attempt_archive,
                description="Refreshes attempt_archive_mv concurrently.",
            ),
            get_operation_info(
                get_attempt_archives,
                description="Batch retrieves archives by IDs from attempt_archive_mv.",
            ),
            get_operation_info(
                search_attempt_archives,
                description="Filtered paginated search against attempt_archive_mv.",
            ),
        ],
    )
