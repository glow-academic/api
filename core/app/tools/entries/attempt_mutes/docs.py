"""Attempt mutes entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.attempt_mutes.create import create_attempt_mutes
from app.tools.entries.attempt_mutes.get import get_attempt_mutes
from app.tools.entries.attempt_mutes.refresh import refresh_attempt_mutes
from app.tools.entries.attempt_mutes.search import (
    search_attempt_mutes_entries_internal,
)


async def get_attempt_mutes_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the attempt_mutes entry."""
    mv_info = await get_mv_info(conn, "attempt_mutes_mv")
    entry_table = await get_table_info(conn, "attempt_mutes_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="attempt_mutes",
        type="entry",
        description=(
            "Mute state records for conversations, tracking whether audio is muted. "
            "Each mute entry references a conversation and maintains a boolean muted flag. "
            "Reads are served from the attempt_mutes_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_attempt_mutes,
                description="Creates a new attempt_mutes entry for a conversation.",
            ),
            get_operation_info(
                refresh_attempt_mutes,
                description="Refreshes attempt_mutes_mv concurrently.",
            ),
            get_operation_info(
                get_attempt_mutes,
                description="Batch retrieves mutes by IDs from attempt_mutes_mv.",
            ),
            get_operation_info(
                search_attempt_mutes_entries_internal,
                description="Filtered paginated search against attempt_mutes_mv.",
            ),
        ],
    )
