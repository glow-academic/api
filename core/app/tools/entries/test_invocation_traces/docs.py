"""Test invocation traces entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.test_invocation_traces.create import (
    create_test_invocation_traces,
)
from app.tools.entries.test_invocation_traces.get import (
    get_test_invocation_traces,
)
from app.tools.entries.test_invocation_traces.refresh import (
    refresh_test_invocation_traces,
)
from app.tools.entries.test_invocation_traces.search import (
    search_test_invocation_traces,
)


async def get_test_invocation_traces_docs(
    conn: asyncpg.Connection,
) -> DocsResponse:
    """Get full documentation for the test_invocation_traces entry."""
    mv_info = await get_mv_info(conn, "test_invocation_traces_mv")
    entry_table = await get_table_info(conn, "test_invocation_traces_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="test_invocation_traces",
        type="entry",
        description=(
            "Test invocation trace — the conversation/bundle context for replay. "
            "Holds the historical run_id we're replaying against and connection-table "
            "config (instructions, prompts, tools, modalities, voices, temperature, "
            "reasoning, qualities). One trace per logical attempt at a test invocation."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_test_invocation_traces,
                description=(
                    "Creates a test_invocation_traces entry binding to a historical "
                    "run_id with optional bundle connection rows."
                ),
            ),
            get_operation_info(
                refresh_test_invocation_traces,
                description="Refreshes test_invocation_traces_mv concurrently.",
            ),
            get_operation_info(
                get_test_invocation_traces,
                description="Batch retrieves test_invocation_traces entries by IDs.",
            ),
            get_operation_info(
                search_test_invocation_traces,
                description="Filtered paginated search against test_invocation_traces_mv.",
            ),
        ],
    )
