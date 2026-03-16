"""Groups CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.groups.types import CreateGroupResponse


async def create_group(
    conn: asyncpg.Connection,
    session_id: UUID,
    id: UUID | None = None,
    name: str = "",
    mcp: bool = False,
    soft: bool = False,
) -> CreateGroupResponse:
    """Create a groups entry."""
    group_id = await conn.fetchval(
        """
        INSERT INTO groups_entry (id, session_id, name, active, mcp, generated)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, true)
        RETURNING id
    """,
        session_id,
        name,
        not soft,
        mcp,
        id,
    )

    if group_id is None:
        raise ValueError("Failed to create groups entry")

    return CreateGroupResponse(id=group_id)
