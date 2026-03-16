"""Attempt chat completion entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.attempt_chat_completion.create import (
    create_attempt_chat_completion,
)
from app.tools.entries.attempt_chat_completion.get import (
    get_attempt_chat_completions,
)
from app.tools.entries.attempt_chat_completion.refresh import (
    refresh_attempt_chat_completion,
)
from app.tools.entries.attempt_chat_completion.search import (
    search_attempt_chat_completions,
)


async def get_attempt_chat_completion_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the attempt_chat_completion entry."""
    mv_info = await get_mv_info(conn, "attempt_chat_completion_mv")
    entry_table = await get_table_info(conn, "attempt_chat_completion_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="attempt_chat_completion",
        type="entry",
        description=(
            "Chat completion records tracking when a chat ends, including stop/error status and message. "
            "Each completion references a chat and is generated from a call. "
            "Reads are served from the attempt_chat_completion_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_attempt_chat_completion,
                description="Creates a new attempt_chat_completion entry for a chat.",
            ),
            get_operation_info(
                refresh_attempt_chat_completion,
                description="Refreshes attempt_chat_completion_mv concurrently.",
            ),
            get_operation_info(
                get_attempt_chat_completions,
                description="Batch retrieves completions by IDs from attempt_chat_completion_mv.",
            ),
            get_operation_info(
                search_attempt_chat_completions,
                description="Filtered paginated search against attempt_chat_completion_mv.",
            ),
        ],
    )
