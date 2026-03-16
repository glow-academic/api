"""Practice chat entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.practice_chat.create import create_practice_chat
from app.tools.entries.practice_chat.get import get_practice_chats
from app.tools.entries.practice_chat.refresh import refresh_practice_chat
from app.tools.entries.practice_chat.search import search_practice_chats


async def get_practice_chat_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the practice chat entry."""
    mv_info = await get_mv_info(conn, "practice_chat_mv")
    entry_table = await get_table_info(conn, "practice_chat_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="practice_chat",
        type="entry",
        description=(
            "Practice chat entries serve as bridge records linking practice sessions to chat sessions. "
            "Each practice_chat_entry connects a practice_entry to a chat_entry for a specific session. "
            "Reads are served from the practice_chat_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_practice_chat,
                description=(
                    "Creates a new practice_chat_entry bridge row linking a practice to a chat session."
                ),
            ),
            get_operation_info(
                refresh_practice_chat,
                description="Refreshes practice_chat_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_practice_chats,
                description="Batch retrieves practice_chat entries by IDs from practice_chat_mv.",
            ),
            get_operation_info(
                search_practice_chats,
                description="Filtered paginated search against practice_chat_mv.",
            ),
        ],
    )
