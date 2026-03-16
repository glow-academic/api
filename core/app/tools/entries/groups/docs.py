"""Groups entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.groups.create import create_group
from app.tools.entries.groups.get import get_groups
from app.tools.entries.groups.refresh import refresh_groups
from app.tools.entries.groups.search import search_groups


async def get_groups_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the groups entry."""
    mv_info = await get_mv_info(conn, "groups_mv")
    entry_table = await get_table_info(conn, "groups_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="groups",
        type="entry",
        description=(
            "Groups represent conversation threads within a session. "
            "Each group belongs to a session and contains runs. "
            "Reads are served from the groups_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_group,
                description="Creates a new group within a session.",
            ),
            get_operation_info(
                refresh_groups,
                description="Refreshes groups_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_groups,
                description="Batch retrieves groups by IDs from groups_mv.",
            ),
            get_operation_info(
                search_groups,
                description="Filtered paginated search against groups_mv.",
            ),
        ],
    )
