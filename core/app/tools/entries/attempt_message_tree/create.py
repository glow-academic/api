"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.attempt_message_tree.types import (
    CreateAttemptMessageTreeResponse,
)


async def create_attempt_message_tree(
    conn: asyncpg.Connection,
    parent_id: UUID,
    child_id: UUID,
    session_id: UUID,
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptMessageTreeResponse | None:
    """Create an attempt_message_tree entry.

    Uses ON CONFLICT (parent_id, child_id) DO NOTHING.
    Returns None if conflict.
    """
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_message_tree_entry (parent_id, child_id, session_id, active, mcp, generated)
        VALUES ($1, $2, $3, $4, $5, true)
        ON CONFLICT (parent_id, child_id) DO NOTHING
        RETURNING parent_id, child_id
        """,
        parent_id,
        child_id,
        session_id,
        not soft,
        mcp,
    )
    if row is None:
        return None
    return CreateAttemptMessageTreeResponse(
        parent_id=row["parent_id"], child_id=row["child_id"]
    )
