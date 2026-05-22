"""Runs CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.runs.types import CreateRunResponse
from app.utils.cache.hedged_row import write_back_row


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
    row = await conn.fetchrow(
        """
        INSERT INTO runs_entry (id, session_id, group_id, active, mcp, generated, created_at)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, true, COALESCE($6, NOW()))
        RETURNING id, created_at
    """,
        session_id,
        group_id,
        not soft,
        mcp,
        id,
        created_at,
    )

    if row is None:
        raise ValueError("Failed to create runs entry")

    run_id = row["id"]
    actual_created_at = row["created_at"]

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

    # Cache-row superset: contains BOTH GET-shape fields (id, session_id,
    # group_id, mcp, generated) AND SEARCH-shape fields (run_id,
    # run_created_at, profiles_id, token counts, model/provider ids,
    # pricing). Aggregates default empty/zero — junction writes that
    # produce token usage / pricing / additional agents must invalidate
    # this row so the next read falls through to the MV.
    fresh_row = {
        # GET shape
        "id": str(run_id),
        "session_id": str(session_id),
        "group_id": str(group_id),
        "mcp": mcp,
        "generated": True,
        # SEARCH shape additions (RunViewItem fields)
        "run_id": str(run_id),
        "run_created_at": actual_created_at.isoformat(),
        "profiles_id": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "cached_input_tokens": 0,
        "agent_ids": [str(a) for a in (agent_ids or [])] or None,
        "model_ids": None,
        "provider_ids": None,
        "pricing": [],
    }
    await write_back_row(
        redis,
        "runs",
        run_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )

    return CreateRunResponse(id=run_id)
