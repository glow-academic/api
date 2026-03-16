"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.attempt_message_tree.types import (
    GetAttemptMessageTreeResponse,
)

MV_NAME = "attempt_message_tree_mv"


async def get_attempt_message_trees(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetAttemptMessageTreeResponse]:
    """Get attempt_message_tree entries by IDs from MV."""
    if not ids:
        return []
    rows = await conn.fetch(f"SELECT * FROM {MV_NAME} WHERE message_id = ANY($1)", ids)
    return [GetAttemptMessageTreeResponse(**dict(r)) for r in rows]
