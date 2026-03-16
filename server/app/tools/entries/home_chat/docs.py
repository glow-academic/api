"""Home chat entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.home_chat.create import create_home_chat
from app.tools.entries.home_chat.get import get_home_chats
from app.tools.entries.home_chat.search import search_home_chats


async def get_home_chat_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the home_chat entry."""
    mv_info = await get_mv_info(conn, "home_chat_mv")
    entry_table = await get_table_info(conn, "home_chat_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="home_chat",
        type="entry",
        description=(
            "Home chat entries act as a bridge between home and chat entities. "
            "Each home_chat entry links a home entry to a chat entry within a session. "
            "Reads are served from the home_chat_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_home_chat,
                description="Creates a new home_chat bridge entry linking home and chat.",
            ),
            get_operation_info(
                get_home_chats,
                description="Batch retrieves home_chat entries by IDs from home_chat_mv.",
            ),
            get_operation_info(
                search_home_chats,
                description="Filtered paginated search against home_chat_mv.",
            ),
        ],
    )
