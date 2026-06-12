"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.file_completion.types import (
    CreateFileCompletionResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_file_completion(
    conn: asyncpg.Connection,
    redis: Redis,
    file_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
    soft: bool = False,
) -> CreateFileCompletionResponse:
    """Create a file_completion entry.

    ``UNIQUE(file_id)`` means at most one completion row per file. A *soft*
    proposal (``active=false``) is MV-invisible but occupies the unique slot. A
    naive ``ON CONFLICT DO NOTHING`` would wedge the file (C1-B, mirroring the
    attempt_completion #339 B1 fix): a later hard complete collides with the
    dormant proposal and no-ops.

    Fix: a hard completion supersedes a DORMANT proposal via
    ``ON CONFLICT DO UPDATE SET active=true`` only when the incoming row is hard
    and the existing row is dormant. An accepted completion is never clobbered,
    a soft proposal never downgrades, and a duplicate hard completion is
    idempotent (no 2nd active row). The returned ``active`` reflects TRUE state.
    """
    incoming_active = not soft
    row = await conn.fetchrow(
        """
        INSERT INTO file_completion_entry (id, file_id, session_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        ON CONFLICT (file_id) DO UPDATE
            SET active = true,
                session_id = EXCLUDED.session_id,
                stop = EXCLUDED.stop,
                error = EXCLUDED.error,
                message = EXCLUDED.message,
                mcp = EXCLUDED.mcp
            WHERE file_completion_entry.active = false
              AND EXCLUDED.active = true
        RETURNING id, created_at, active, stop, error, message, mcp, session_id
        """,
        file_id,
        session_id,
        stop,
        error,
        message,
        incoming_active,
        mcp,
        id,
    )

    if row is None:
        # Conflict that neither inserted nor superseded: incoming soft proposal,
        # or the existing row is already an accepted completion. Return the
        # row's TRUE current state.
        existing = await conn.fetchrow(
            "SELECT id, active FROM file_completion_entry WHERE file_id = $1",
            file_id,
        )
        return CreateFileCompletionResponse(
            id=existing["id"], active=existing["active"]
        )

    entry_id = row["id"]
    created_at = row["created_at"]

    fresh_row = {
        "id": str(entry_id),
        "file_id": str(file_id),
        "stop": row["stop"],
        "error": row["error"],
        "message": row["message"],
        "session_id": str(row["session_id"]),
        "created_at": created_at.isoformat(),
        "active": row["active"],
        "generated": True,
        "mcp": row["mcp"],
    }
    await write_back_row(
        redis,
        "file_completion",
        entry_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateFileCompletionResponse(id=entry_id, active=row["active"])
