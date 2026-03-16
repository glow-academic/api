"""Attempt conversation completion entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.attempt_conversation_completion.create import (
    create_attempt_conversation_completion,
)
from app.tools.entries.attempt_conversation_completion.get import (
    get_attempt_conversation_completions,
)
from app.tools.entries.attempt_conversation_completion.refresh import (
    refresh_attempt_conversation_completion,
)
from app.tools.entries.attempt_conversation_completion.search import (
    search_attempt_conversation_completions,
)


async def get_attempt_conversation_completion_docs(
    conn: asyncpg.Connection,
) -> DocsResponse:
    """Get full documentation for the attempt_conversation_completion entry."""
    mv_info = await get_mv_info(conn, "attempt_conversation_completion_mv")
    entry_table = await get_table_info(conn, "attempt_conversation_completion_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="attempt_conversation_completion",
        type="entry",
        description=(
            "Conversation completion records tracking when a conversation ends "
            "with stop/error status and a message. Each completion references a conversation. "
            "Reads are served from the attempt_conversation_completion_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_attempt_conversation_completion,
                description="Creates a new attempt_conversation_completion entry.",
            ),
            get_operation_info(
                refresh_attempt_conversation_completion,
                description="Refreshes attempt_conversation_completion_mv concurrently.",
            ),
            get_operation_info(
                get_attempt_conversation_completions,
                description="Batch retrieves completions by IDs from the materialized view.",
            ),
            get_operation_info(
                search_attempt_conversation_completions,
                description="Filtered paginated search against attempt_conversation_completion_mv.",
            ),
        ],
    )
