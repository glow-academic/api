"""Messages CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.messages.types import CreateMessageResponse
from app.utils.cache.hedged_row import write_back_row


async def create_message(
    conn: asyncpg.Connection,
    redis: Redis,
    run_id: UUID,
    role: str,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    reasoning: bool = False,
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

    ``reasoning`` flags the row as a chain-of-thought trace. Defaults to
    false so all existing callers keep producing normal messages. Set to
    true only when persisting the model's intermediate thinking output
    (e.g. Gemma 4 / GPT-5 reasoning channels) — the FE can collapse such
    rows independently of the final answer.
    """
    row = await conn.fetchrow(
        """
        INSERT INTO messages_entry (id, run_id, role, active, mcp, generated, reasoning, created_at)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, true, $7, COALESCE($6, now()))
        RETURNING id, created_at
    """,
        run_id,
        role,
        not soft,
        mcp,
        id,
        created_at,
        reasoning,
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

    fresh_row = {
        "id": str(row["id"]),
        "run_id": str(run_id),
        "role": role,
        "created_at": row["created_at"].isoformat(),
        "active": not soft,
        "mcp": mcp,
        "generated": True,
        "agent_ids": [str(a) for a in (agent_ids or [])],
    }
    await write_back_row(
        redis,
        "messages",
        row["id"],
        fresh_row,
        score_ms=int(row["created_at"].timestamp() * 1000),
    )

    return CreateMessageResponse(id=row["id"], created_at=row["created_at"])
