"""Messages GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.messages.types import GetMessageResponse
from app.utils.cache.hedged_row import read_back_row


async def get_message(
    conn: asyncpg.Connection,
    message_id: UUID,
    redis: Redis,
    agents: bool = False,
    *,
    bypass_cache: bool = False,
) -> GetMessageResponse | None:
    """Get a messages entry by ID, optionally with agent connections."""
    if not bypass_cache:
        cached = await read_back_row(redis, "messages", message_id)
        if cached is not None:
            resp = GetMessageResponse.model_validate(cached)
            if not agents:
                resp = resp.model_copy(update={"agent_ids": []})
            return resp

    row = await conn.fetchrow(
        """
        SELECT m.id, m.run_id, m.role, m.created_at, m.active, m.mcp, m.generated,
               COALESCE(ARRAY_AGG(DISTINCT mac.agents_id) FILTER (WHERE mac.agents_id IS NOT NULL), '{}') AS agent_ids
        FROM messages_entry m
        LEFT JOIN messages_agents_connection mac ON mac.message_id = m.id
        WHERE m.id = $1
        GROUP BY m.id, m.run_id, m.role, m.created_at, m.active, m.mcp, m.generated
    """,
        message_id,
    )

    if row is None:
        return None

    return GetMessageResponse(
        id=row["id"],
        run_id=row["run_id"],
        role=str(row["role"]),
        created_at=row["created_at"],
        active=row["active"],
        mcp=row["mcp"],
        generated=row["generated"],
        agent_ids=row["agent_ids"] if agents else [],
    )
