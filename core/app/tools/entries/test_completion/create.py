"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.test_completion.types import (
    CreateTestCompletionResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_test_completion(
    conn: asyncpg.Connection,
    redis: Redis,
    test_id: UUID,
    call_id: UUID,
    *,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
    soft: bool = False,
) -> CreateTestCompletionResponse:
    """Create a test_completion entry.

    ``UNIQUE(test_id)`` means at most one completion row per test. A *soft*
    proposal (``active=false``) is MV-invisible — the test still reads "not
    completed" — but it occupies the unique slot. A naive
    ``ON CONFLICT DO NOTHING`` then permanently wedges the test: a later hard
    complete (``active=true``) collides with the dormant proposal, no-ops, and
    the test can never reach the completed terminal state (C1-B, mirroring the
    attempt_completion #339 B1 fix).

    Fix: a real (hard) completion *supersedes* a DORMANT proposal —
    ``ON CONFLICT DO UPDATE SET active=true`` but only when the incoming row is
    hard and the existing row is dormant. A legitimately-accepted completion
    (``active=true``) is never clobbered, and a soft proposal never downgrades
    an existing row. A duplicate hard completion is idempotent (no 2nd active
    row). The returned ``active`` reflects the row's TRUE state.
    """
    incoming_active = not soft
    row = await conn.fetchrow(
        """
        INSERT INTO test_completion_entry (id, test_id, call_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        ON CONFLICT (test_id) DO UPDATE
            SET active = true,
                call_id = EXCLUDED.call_id,
                stop = EXCLUDED.stop,
                error = EXCLUDED.error,
                message = EXCLUDED.message,
                mcp = EXCLUDED.mcp
            WHERE test_completion_entry.active = false
              AND EXCLUDED.active = true
        RETURNING id, created_at, active, stop, error, message, mcp, call_id
        """,
        test_id,
        call_id,
        stop,
        error,
        message,
        incoming_active,
        mcp,
        id,
    )

    if row is None:
        # Conflict that neither inserted nor superseded: incoming soft proposal,
        # or the existing row is already an accepted (active=true) completion.
        # Return the row's TRUE current state so the caller does not mistake a
        # dormant/unchanged slot for a fresh successful completion.
        existing = await conn.fetchrow(
            "SELECT id, active FROM test_completion_entry WHERE test_id = $1",
            test_id,
        )
        return CreateTestCompletionResponse(
            id=existing["id"], active=existing["active"]
        )

    entry_id = row["id"]
    created_at = row["created_at"]

    fresh_row = {
        "id": str(entry_id),
        "test_id": str(test_id),
        "stop": row["stop"],
        "error": row["error"],
        "message": row["message"],
        "call_id": str(row["call_id"]),
        "created_at": created_at.isoformat(),
        "active": row["active"],
        "generated": True,
        "mcp": row["mcp"],
    }
    await write_back_row(
        redis,
        "test_completion",
        entry_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateTestCompletionResponse(id=entry_id, active=row["active"])
