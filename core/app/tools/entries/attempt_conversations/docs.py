"""Attempt conversations entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.attempt_conversations.create import (
    create_attempt_conversations,
)
from app.tools.entries.attempt_conversations.get import (
    get_attempt_conversations,
)
from app.tools.entries.attempt_conversations.refresh import (
    refresh_attempt_conversations,
)
from app.tools.entries.attempt_conversations.search import (
    search_attempt_conversations,
)


async def get_attempt_conversations_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the attempt_conversations entry."""
    mv_info = await get_mv_info(conn, "attempt_conversations_mv")
    entry_table = await get_table_info(conn, "attempt_conversations_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="attempt_conversations",
        type="entry",
        description=(
            "Individual conversations within chats, linking a chat to a run. "
            "Each conversation represents an interaction session within a chat. "
            "Reads are served from the attempt_conversations_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_attempt_conversations,
                description="Creates a new attempt_conversations entry linking a chat to a run.",
            ),
            get_operation_info(
                refresh_attempt_conversations,
                description="Refreshes attempt_conversations_mv concurrently.",
            ),
            get_operation_info(
                get_attempt_conversations,
                description="Batch retrieves conversations by IDs from attempt_conversations_mv.",
            ),
            get_operation_info(
                search_attempt_conversations,
                description="Filtered paginated search against attempt_conversations_mv.",
            ),
        ],
    )
