"""Attempt chat bridge entry documentation."""

import asyncpg  # type: ignore

from app.infra.docs.get_mv_info import get_mv_info
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.get_table_info import get_table_info
from app.infra.docs.types import DocsResponse
from app.tools.entries.attempt_chat_bridge.create import (
    create_attempt_chat_bridge,
)
from app.tools.entries.attempt_chat_bridge.get import (
    get_attempt_chat_bridge,
)
from app.tools.entries.attempt_chat_bridge.refresh import (
    refresh_attempt_chat_bridge,
)
from app.tools.entries.attempt_chat_bridge.search import (
    search_attempt_chat_bridges,
)


async def get_attempt_chat_bridge_docs(conn: asyncpg.Connection) -> DocsResponse:
    """Get full documentation for the attempt_chat_bridge entry."""
    mv_info = await get_mv_info(conn, "attempt_chat_bridge_mv")
    entry_table = await get_table_info(conn, "attempt_chat_bridge_entry")

    tables = [t for t in [entry_table] if t is not None]

    return DocsResponse(
        name="attempt_chat_bridge",
        type="entry",
        description=(
            "Attempt chat bridge entries link attempts to chats via a session. "
            "This bridge table connects the attempt and chat domains. "
            "Reads are served from the attempt_chat_bridge_mv materialized view."
        ),
        materialized_view=mv_info,
        tables=tables,
        operations=[
            get_operation_info(
                create_attempt_chat_bridge,
                description=(
                    "Creates a new attempt_chat_bridge entry linking an attempt "
                    "to a chat within a session."
                ),
            ),
            get_operation_info(
                get_attempt_chat_bridge,
                description="Retrieves attempt_chat_bridge entries by attempt IDs from MV.",
            ),
            get_operation_info(
                refresh_attempt_chat_bridge,
                description="Refreshes attempt_chat_bridge_mv concurrently to reflect latest writes.",
            ),
            get_operation_info(
                search_attempt_chat_bridges,
                description="Filtered paginated search against attempt_chat_bridge_mv.",
            ),
        ],
    )
