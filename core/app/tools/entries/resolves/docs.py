"""Resolves entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.resolves.create import create_resolve
from app.tools.entries.resolves.get import get_resolves
from app.tools.entries.resolves.refresh import refresh_resolves
from app.tools.entries.resolves.search import search_resolves


async def get_resolves_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the resolves entry."""
    mv_info = await get_mv_info(conn, "resolves_mv")
    entry_table = await get_table_info(conn, "resolves_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="resolves",
        type="entry",
        description=(
            "Resolves entries record whether a problem has been resolved. "
            "Each entry links to a problem and optionally to a call. "
            "Reads are served from the resolves_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_resolve,
                description="Creates a new resolve entry for a problem.",
            ),
            get_operation_info(
                refresh_resolves,
                description="Refreshes resolves_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_resolves,
                description="Batch retrieves resolves by IDs from resolves_mv.",
            ),
            get_operation_info(
                search_resolves,
                description="Filtered paginated search against resolves_mv.",
            ),
        ],
    )
