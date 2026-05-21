"""Runs CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.runs.types import CreateRunResponse


async def create_run(
    conn: asyncpg.Connection,
    redis: Redis,
    group_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    agent_ids: list[UUID] | None = None,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateRunResponse:
    """Create a runs entry with optional agent links."""
    run_id = await conn.fetchval(
        """
        INSERT INTO runs_entry (id, session_id, group_id, active, mcp, generated, created_at)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, true, COALESCE($6, NOW()))
        RETURNING id
    """,
        session_id,
        group_id,
        not soft,
        mcp,
        id,
        created_at,
    )

    if run_id is None:
        raise ValueError("Failed to create runs entry")

    # Link run → agents_resource
    if agent_ids:
        await conn.execute(
            """INSERT INTO runs_agents_connection (run_id, agents_id, created_at, active, generated, mcp)
            SELECT $1, a.id, COALESCE($4, NOW()), true, false, $2
            FROM agents_resource a
            WHERE a.id = ANY($3::uuid[])
            ON CONFLICT (run_id, agents_id) DO NOTHING""",
            run_id,
            mcp,
            agent_ids,
            created_at,
        )

    return CreateRunResponse(id=run_id)
