"""Group names CREATE — append a new name entry for a group."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.group_names.types import CreateGroupNameResponse


async def create_group_name(
    conn: asyncpg.Connection,
    group_id: UUID,
    name: str,
    session_id: UUID,
    id: UUID | None = None,
    generated: bool = False,
    mcp: bool = False,
) -> CreateGroupNameResponse:
    """Create a group_names entry (append-only)."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO group_names_entry (id, group_id, name, session_id, generated, mcp)
        VALUES (COALESCE($1, uuidv7()), $2, $3, $4, $5, $6)
        RETURNING id
        """,
        id,
        group_id,
        name,
        session_id,
        generated,
        mcp,
    )

    if entry_id is None:
        raise ValueError("Failed to create group_names entry")

    return CreateGroupNameResponse(id=entry_id)
