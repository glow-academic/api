"""Messages CREATE — reusable data-access layer."""

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
) -> CreateMessageResponse:
    """Create a messages entry with optional agent connections."""
    row = await conn.fetchrow(
        """
        INSERT INTO messages_entry (id, run_id, role, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2::message_type, $3, $4, true)
        RETURNING id, created_at
    """,
        run_id,
        role,
        not soft,
        mcp,
        id,
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
