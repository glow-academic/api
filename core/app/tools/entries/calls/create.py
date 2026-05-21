"""Calls CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.calls.types import CreateCallResponse


async def create_call(
    conn: asyncpg.Connection,
    redis: Redis,
    run_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    external_call_id: str = "",
    tool_id: UUID | None = None,
    operation_key: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateCallResponse:
    """Create a calls entry with optional tool link."""
    call_id = await conn.fetchval(
        """
        INSERT INTO calls_entry (id, run_id, session_id, external_call_id, active, mcp, generated, operation_key, created_at)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true, COALESCE($7, uuidv7()), COALESCE($8, NOW()))
        RETURNING id
    """,
        run_id,
        session_id,
        external_call_id,
        not soft,
        mcp,
        id,
        operation_key,
        created_at,
    )

    if call_id is None:
        raise ValueError("Failed to create calls entry")

    # Link call → tools_resource
    if tool_id is not None:
        await conn.execute(
            """
            INSERT INTO tools_calls_connection (tools_id, call_id)
            VALUES ($1, $2)
        """,
            tool_id,
            call_id,
        )

    return CreateCallResponse(id=call_id)
