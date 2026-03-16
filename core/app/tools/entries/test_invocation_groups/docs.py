"""Test invocation groups entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.test_invocation_groups.create import (
    create_test_invocation_groups,
)
from app.tools.entries.test_invocation_groups.get import (
    get_test_invocation_groups,
)
from app.tools.entries.test_invocation_groups.refresh import (
    refresh_test_invocation_groups,
)
from app.tools.entries.test_invocation_groups.search import (
    search_test_invocation_groups,
)


async def get_test_invocation_groups_docs(
    conn: asyncpg.Connection,
) -> DocsResponse:
    """Get full documentation for the test_invocation_groups entry."""
    mv_info = await get_mv_info(conn, "test_invocation_groups_mv")
    entry_table = await get_table_info(conn, "test_invocation_groups_entry")
    agents_connection = await get_table_info(
        conn, "test_invocation_groups_agents_connection"
    )
    groups_connection = await get_table_info(
        conn, "test_invocation_groups_groups_connection"
    )

    tables = [
        t for t in [entry_table, agents_connection, groups_connection] if t is not None
    ]

    return DocsResponse(
        name="test_invocation_groups",
        type="entry",
        description=(
            "Test invocation group assignments. Maps test invocations to agent groups and agents. "
            "Allows specifying which agents and groups participate in a test invocation scenario. "
            "Reads are served from the test_invocation_groups_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_test_invocation_groups,
                description=(
                    "Creates a test_invocation_groups entry with optional agent_ids and group_ids "
                    "connections to agents and groups."
                ),
            ),
            get_operation_info(
                refresh_test_invocation_groups,
                description="Refreshes test_invocation_groups_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_test_invocation_groups,
                description="Batch retrieves test_invocation_groups entries by IDs from test_invocation_groups_mv.",
            ),
            get_operation_info(
                search_test_invocation_groups,
                description="Filtered paginated search against test_invocation_groups_mv.",
            ),
        ],
    )
