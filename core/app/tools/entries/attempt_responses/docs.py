"""Attempt responses entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.attempt_responses.create import (
    create_attempt_responses,
)
from app.tools.entries.attempt_responses.get import get_attempt_responses
from app.tools.entries.attempt_responses.refresh import (
    refresh_attempt_responses,
)
from app.tools.entries.attempt_responses.search import (
    search_attempt_responses,
)


async def get_attempt_responses_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the attempt_responses entry."""
    mv_info = await get_mv_info(conn, "attempt_responses_mv")
    entry_table = await get_table_info(conn, "attempt_responses_entry")
    conn_q_table = await get_table_info(conn, "attempt_responses_questions_connection")
    conn_o_table = await get_table_info(conn, "attempt_responses_options_connection")

    tables = [t for t in [entry_table, conn_q_table, conn_o_table] if t is not None]

    return DocsResponse(
        name="attempt_responses",
        type="entry",
        description=(
            "Response records capturing answer selections within chats. "
            "Each response entry references a chat and optionally links to questions "
            "and options via connection tables. "
            "Reads are served from the attempt_responses_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_attempt_responses,
                description=(
                    "Creates a new attempt_responses entry for a chat and "
                    "optionally populates attempt_responses_questions_connection "
                    "and attempt_responses_options_connection."
                ),
            ),
            get_operation_info(
                refresh_attempt_responses,
                description="Refreshes attempt_responses_mv concurrently.",
            ),
            get_operation_info(
                get_attempt_responses,
                description="Batch retrieves responses by IDs from attempt_responses_mv.",
            ),
            get_operation_info(
                search_attempt_responses,
                description="Filtered paginated search against attempt_responses_mv.",
            ),
        ],
    )
