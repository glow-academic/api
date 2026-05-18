"""Attempt message tree entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.attempt_message_tree.create import (
    create_attempt_message_tree,
)
from app.tools.entries.attempt_message_tree.get import (
    get_attempt_message_trees,
)
from app.tools.entries.attempt_message_tree.refresh import (
    refresh_attempt_message_tree,
)
from app.tools.entries.attempt_message_tree.search import (
    search_attempt_message_trees,
)


async def get_attempt_message_tree_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the attempt_message_tree entry."""
    mv_info = await get_mv_info(conn, "attempt_message_tree_mv")
    entry_table = await get_table_info(conn, "attempt_message_tree_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="attempt_message_tree",
        type="entry",
        description=(
            "Hierarchical relationships between messages, tracking parent-child links "
            "within a message tree for branching conversations. "
            "Each entry maintains parent and child message IDs plus a session reference. "
            "Uses conflict detection to prevent duplicate relationships. "
            "Reads are served from the attempt_message_tree_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_attempt_message_tree,
                description=(
                    "Creates a new attempt_message_tree entry with conflict detection; "
                    "returns None if the parent-child link already exists."
                ),
            ),
            get_operation_info(
                refresh_attempt_message_tree,
                description="Refreshes attempt_message_tree_mv concurrently.",
            ),
            get_operation_info(
                get_attempt_message_trees,
                description="Batch retrieves message trees by IDs from attempt_message_tree_mv.",
            ),
            get_operation_info(
                search_attempt_message_trees,
                description="Filtered paginated search against attempt_message_tree_mv.",
            ),
        ],
    )
