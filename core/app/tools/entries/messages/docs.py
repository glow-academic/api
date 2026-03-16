"""Messages entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.messages.create import create_message
from app.tools.entries.messages.get import get_message
from app.tools.entries.messages.search import search_messages


async def get_messages_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the messages entry."""
    entry_table = await get_table_info(conn, "messages_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="messages",
        type="entry",
        description=(
            "Message entries track individual chat messages with their role and timestamp. "
            "Each message is associated with a run and stores role information (user, assistant, system). "
            "Reads are served directly from the messages_entry table."
        ),
        materialized_view=None,
        tables=tables,
        operations=[
            get_operation_info(
                create_message,
                description="Creates a new message entry with role type in messages_entry table.",
            ),
            get_operation_info(
                get_message,
                description="Retrieves a single message entry by ID from messages_entry.",
            ),
            get_operation_info(
                search_messages,
                description="Filtered paginated search against messages_mv.",
            ),
        ],
    )
