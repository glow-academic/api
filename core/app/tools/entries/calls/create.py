"""Calls CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.calls.types import CreateCallResponse
from app.utils.cache.hedged_row import write_back_row


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
    row = await conn.fetchrow(
        """
        INSERT INTO calls_entry (id, run_id, session_id, external_call_id, active, mcp, generated, operation_key, created_at)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true, COALESCE($7, uuidv7()), COALESCE($8, NOW()))
        RETURNING id, created_at, operation_key
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

    if row is None:
        raise ValueError("Failed to create calls entry")

    call_id = row["id"]
    actual_created_at = row["created_at"]
    actual_op_key = row["operation_key"]

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

    # Write-back cache row matching get/search MV shape. Upload denormalized
    # fields are None at create-time (uploads link in via separate flow).
    fresh_row = {
        "id": str(call_id),
        "run_id": str(run_id),
        "created_at": actual_created_at.isoformat(),
        "operation_key": str(actual_op_key) if actual_op_key else None,
        "upload_id": None,
        "file_path": None,
        "mime_type": None,
        "tool_id": str(tool_id) if tool_id else None,
    }
    await write_back_row(
        redis,
        "calls",
        call_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )

    return CreateCallResponse(id=call_id)
