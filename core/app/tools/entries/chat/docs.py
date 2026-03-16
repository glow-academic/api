"""Chat entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.chat.create import create_chat
from app.tools.entries.chat.get import get_chats
from app.tools.entries.chat.refresh import refresh_chat
from app.tools.entries.chat.search import search_chat_entries_internal


async def get_chat_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the chat entry."""
    mv_info = await get_mv_info(conn, "chat_mv")
    entry_table = await get_table_info(conn, "chat_entry")
    scenarios_connection = await get_table_info(conn, "chat_scenarios_connection")
    departments_connection = await get_table_info(conn, "chat_departments_connection")

    tables = [
        t
        for t in [entry_table, scenarios_connection, departments_connection]
        if t is not None
    ]

    return DocsResponse(
        name="chat",
        type="entry",
        description=(
            "Chat entries represent conversational interactions within sessions. "
            "Each chat can be linked to scenarios and departments via connection tables. "
            "Reads are served from the chat_mv materialized view which includes all related resource IDs."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_chat,
                description=(
                    "Creates a new chat entry with optional connections to scenarios "
                    "and departments."
                ),
            ),
            get_operation_info(
                refresh_chat,
                description="Refreshes chat_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                get_chats,
                description="Batch retrieves chat entries by IDs from chat_mv with all resource IDs.",
            ),
            get_operation_info(
                search_chat_entries_internal,
                description="Filtered paginated search against chat_mv.",
            ),
        ],
    )
