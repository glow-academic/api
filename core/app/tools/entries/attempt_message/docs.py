"""Attempt message entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.attempt_message.create import create_attempt_message
from app.tools.entries.attempt_message.get import get_attempt_messages
from app.tools.entries.attempt_message.refresh import refresh_attempt_message
from app.tools.entries.attempt_message.search import search_attempt_messages


async def get_attempt_message_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the attempt_message entry."""
    mv_info = await get_mv_info(conn, "attempt_message_mv")
    entry_table = await get_table_info(conn, "attempt_message_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="attempt_message",
        type="entry",
        description=(
            "Individual messages within chats, associating message IDs with attempt chats. "
            "Each entry links a base message to a specific chat and records "
            "when the message was created via a call. "
            "Reads are served from the attempt_message_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_attempt_message,
                description="Creates a new attempt_message entry linking a message to a chat.",
            ),
            get_operation_info(
                refresh_attempt_message,
                description="Refreshes attempt_message_mv concurrently.",
            ),
            get_operation_info(
                get_attempt_messages,
                description="Batch retrieves messages by IDs from attempt_message_mv.",
            ),
            get_operation_info(
                search_attempt_messages,
                description="Filtered paginated search against attempt_message_mv.",
            ),
        ],
    )
