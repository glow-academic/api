"""Run pricing entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.run_pricing.create import (
    create_run_pricing_entry_internal,
)
from app.tools.entries.run_pricing.get import get_run_pricing_entries_internal
from app.tools.entries.run_pricing.refresh import refresh_run_pricing_internal
from app.tools.entries.run_pricing.search import (
    search_run_pricing_entries_internal,
)


async def get_run_pricing_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the run pricing entry."""
    mv_info = await get_mv_info(conn, "run_pricing_mv")
    entry_table = await get_table_info(conn, "run_pricing_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="run_pricing",
        type="entry",
        description=(
            "Run pricing entries track pricing information for runs, categorized by pricing_type. "
            "Each entry records a count of pricing units consumed for a specific run and pricing category. "
            "This is an append-only table — pricing entries are never mutated. "
            "Reads are served from the run_pricing_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_run_pricing_entry_internal,
                description=(
                    "Creates a new run_pricing entry for a specific run and pricing_type. "
                    "Internal only — no HTTP route."
                ),
            ),
            get_operation_info(
                refresh_run_pricing_internal,
                description="Refreshes run_pricing_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_run_pricing_entries_internal,
                description="Batch retrieves run_pricing entries by IDs from run_pricing_mv.",
            ),
            get_operation_info(
                search_run_pricing_entries_internal,
                description="Filtered paginated search against run_pricing_mv.",
            ),
        ],
    )
