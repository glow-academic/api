"""Test archive entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.test_archive.create import create_test_archive
from app.tools.entries.test_archive.get import get_test_archives
from app.tools.entries.test_archive.refresh import refresh_test_archive
from app.tools.entries.test_archive.search import search_test_archives


async def get_test_archive_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the test_archive entry."""
    mv_info = await get_mv_info(conn, "test_archive_mv")
    entry_table = await get_table_info(conn, "test_archive_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="test_archive",
        type="entry",
        description=(
            "Test archive status tracking. Records when tests are archived/unarchived. "
            "Each entry links to a test and tracks the archived flag state. "
            "Reads are served from the test_archive_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_test_archive,
                description=(
                    "Creates a test_archive entry with test_id and archived status flag."
                ),
            ),
            get_operation_info(
                refresh_test_archive,
                description="Refreshes test_archive_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_test_archives,
                description="Batch retrieves test_archive entries by IDs from test_archive_mv.",
            ),
            get_operation_info(
                search_test_archives,
                description="Filtered paginated search against test_archive_mv.",
            ),
        ],
    )
