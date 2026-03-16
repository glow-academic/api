"""Metrics entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.metrics.create import create_metrics_entry_internal
from app.tools.entries.metrics.get import get_metrics
from app.tools.entries.metrics.search import search_metrics


async def get_metrics_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the metrics entry."""
    mv_info = await get_mv_info(conn, "metrics_mv")
    entry_table = await get_table_info(conn, "metrics_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="metrics",
        type="entry",
        description=(
            "Metrics entries track system performance and resource usage over time. "
            "Each metrics entry stores request counts, error counts, latency, CPU, and memory information. "
            "This is an internal-only entry with no public HTTP routes. "
            "Reads are served from the metrics_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_metrics_entry_internal,
                description="Creates a new metrics entry with system performance data (internal only).",
            ),
            get_operation_info(
                get_metrics,
                description="Batch retrieves metrics entries by date_hour IDs from metrics_mv.",
            ),
            get_operation_info(
                search_metrics,
                description="Filtered paginated search against metrics_mv.",
            ),
        ],
    )
