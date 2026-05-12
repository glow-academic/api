"""Messages CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.messages.types import CreateMessageResponse


async def create_message(
    conn: asyncpg.Connection,
    run_id: UUID,
    role: str,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    agent_ids: list[UUID] | None = None,
    created_at: datetime | None = None,
) -> CreateMessageResponse:
    """Create a messages entry with optional agent connections.

    ``created_at`` lets callers override the row timestamp. Needed so the
    audit-side tool-call message (written by ``create_tool_call`` AFTER
    ``await runner()`` completes) can sort at *dispatch* time rather than
    the audit-write completion time. Without the override the row is
    stamped ``now()``, which sorts after the nested run's outputs and
    renders the tool-call indicator below its own produced media in the
    FE chat panel.
    """
    row = await conn.fetchrow(
        """
        INSERT INTO messages_entry (id, run_id, role, active, mcp, generated, created_at)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, true, COALESCE($6, now()))
        RETURNING id, created_at
    """,
        run_id,
        role,
        not soft,
        mcp,
        id,
        created_at,
    )

    if row is None:
        raise ValueError("Failed to create messages entry")

    if agent_ids:
        for agent_id in agent_ids:
            await conn.execute(
                """
                INSERT INTO messages_agents_connection (message_id, agents_id)
                VALUES ($1, $2)
                """,
                row["id"],
                agent_id,
            )

    return CreateMessageResponse(id=row["id"], created_at=row["created_at"])
