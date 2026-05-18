"""Attempt hint entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.attempt_hint.create import create_attempt_hint
from app.tools.entries.attempt_hint.get import get_attempt_hints
from app.tools.entries.attempt_hint.refresh import refresh_attempt_hint
from app.tools.entries.attempt_hint.search import search_attempt_hints


async def get_attempt_hint_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the attempt_hint entry."""
    mv_info = await get_mv_info(conn, "attempt_hint_mv")
    entry_table = await get_table_info(conn, "attempt_hint_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="attempt_hint",
        type="entry",
        description=(
            "Hint records attached to messages, providing contextual guidance. "
            "Each hint references a message and contains the hint text. "
            "Reads are served from the attempt_hint_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_attempt_hint,
                description="Creates a new attempt_hint entry for a message.",
            ),
            get_operation_info(
                refresh_attempt_hint,
                description="Refreshes attempt_hint_mv concurrently.",
            ),
            get_operation_info(
                get_attempt_hints,
                description="Batch retrieves hints by IDs from attempt_hint_mv.",
            ),
            get_operation_info(
                search_attempt_hints,
                description="Filtered paginated search against attempt_hint_mv.",
            ),
        ],
    )
