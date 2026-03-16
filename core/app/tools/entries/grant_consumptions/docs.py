"""Grant consumptions entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.grant_consumptions.create import (
    create_grant_consumption,
)
from app.tools.entries.grant_consumptions.get import get_grant_consumptions
from app.tools.entries.grant_consumptions.search import (
    search_grant_consumptions,
)


async def get_grant_consumptions_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the grant consumptions entry."""
    entry_table = await get_table_info(conn, "grant_consumptions_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="grant_consumptions",
        type="entry",
        description=(
            "Grant consumption entries track when a grant is consumed. "
            "This is an append-only table — instead of mutating grants_entry, "
            "each consumption is recorded as a separate row. "
            "Reads are served directly from the grant_consumptions_entry table."
        ),
        materialized_view=None,
        tables=tables,
        operations=[
            get_operation_info(
                create_grant_consumption,
                description="Creates a new grant consumption entry for a grant.",
            ),
            get_operation_info(
                get_grant_consumptions,
                description="Batch retrieves grant consumption entries by IDs.",
            ),
            get_operation_info(
                search_grant_consumptions,
                description="Filtered paginated search against grant_consumptions_entry.",
            ),
        ],
    )
