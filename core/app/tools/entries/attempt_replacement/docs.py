"""Attempt replacement entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.attempt_replacement.create import (
    create_attempt_replacement,
)
from app.tools.entries.attempt_replacement.get import get_attempt_replacements
from app.tools.entries.attempt_replacement.refresh import (
    refresh_attempt_replacement,
)
from app.tools.entries.attempt_replacement.search import (
    search_attempt_replacements,
)


async def get_attempt_replacement_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the attempt_replacement entry."""
    mv_info = await get_mv_info(conn, "attempt_replacement_mv")
    entry_table = await get_table_info(conn, "attempt_replacement_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="attempt_replacement",
        type="entry",
        description=(
            "Replacement suggestions within improvements, detailing specific text "
            "changes and sections to improve. Each replacement references an improvement, "
            "includes the replacement text, section identifier, and an index for ordering. "
            "Reads are served from the attempt_replacement_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_attempt_replacement,
                description="Creates a new attempt_replacement entry within an improvement.",
            ),
            get_operation_info(
                refresh_attempt_replacement,
                description="Refreshes attempt_replacement_mv concurrently.",
            ),
            get_operation_info(
                get_attempt_replacements,
                description="Batch retrieves replacements by IDs from attempt_replacement_mv.",
            ),
            get_operation_info(
                search_attempt_replacements,
                description="Filtered paginated search against attempt_replacement_mv.",
            ),
        ],
    )
