"""attempt_mutes/search — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

MV_NAME = "attempt_mutes_mv"


async def search_attempt_mutes_entries_internal(
    conn: asyncpg.Connection,
    conversation_ids: list[UUID] | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
) -> list[dict]:
    """Search attempt_mutes entries from attempt_mutes_mv."""
    rows = await conn.fetch(
        f"""
        SELECT id, created_at, generated, mcp, active,
               conversation_id, muted, call_id
        FROM {MV_NAME}
        WHERE ($1::uuid[] IS NULL OR conversation_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        conversation_ids,
        limit_count,
        offset_count,
    )

    return [dict(r) for r in rows]
