"""Entry CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_completion.types import (
    CreateAttemptCompletionResponse,
)
from app.utils.cache.hedged_row import invalidate_row, write_back_row


async def create_attempt_completion(
    conn: asyncpg.Connection,
    redis: Redis,
    attempt_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateAttemptCompletionResponse:
    """Create a attempt_completion entry.

    ``UNIQUE(attempt_id)`` means at most one completion row per attempt. A
    *soft* proposal (``active=false``) is MV-invisible — the attempt still reads
    "not completed" — but it occupies the unique slot. A naive
    ``ON CONFLICT DO NOTHING`` then permanently wedges the attempt: a later hard
    complete (``active=true``) collides with the dormant proposal, no-ops, and
    the attempt can never reach the completed terminal state (B1).

    Fix: a real (hard) completion *supersedes* a DORMANT proposal —
    ``ON CONFLICT DO UPDATE SET active=true`` but only when the incoming row is
    hard and the existing row is dormant. A legitimately-accepted completion
    (``active=true``) is never clobbered, and a soft proposal never downgrades
    an existing row. The returned ``active`` reflects the row's TRUE state so the
    caller can tell whether the completion actually took effect — we no longer
    report a dormant row as a successful completion.
    """
    incoming_active = not soft
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_completion_entry (id, attempt_id, session_id, stop, error, message, active, mcp, generated, created_at)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true, COALESCE($9, NOW()))
        ON CONFLICT (attempt_id) DO UPDATE
            SET active = true,
                session_id = EXCLUDED.session_id,
                stop = EXCLUDED.stop,
                error = EXCLUDED.error,
                message = EXCLUDED.message,
                mcp = EXCLUDED.mcp,
                created_at = EXCLUDED.created_at
            WHERE attempt_completion_entry.active = false
              AND EXCLUDED.active = true
        RETURNING id, created_at, active, stop, error, message, mcp
        """,
        attempt_id,
        session_id,
        stop,
        error,
        message,
        incoming_active,
        mcp,
        id,
        created_at,
    )
    if row is None:
        # Conflict that neither inserted nor superseded: either the incoming row
        # is soft (a proposal must not downgrade/touch an existing slot), or the
        # existing row is already an accepted (active=true) completion. Return
        # the row's TRUE current state so the caller does not mistake a dormant
        # or unchanged slot for a fresh successful completion.
        existing = await conn.fetchrow(
            "SELECT id, active FROM attempt_completion_entry WHERE attempt_id = $1",
            attempt_id,
        )
        return CreateAttemptCompletionResponse(
            id=existing["id"], active=existing["active"]
        )

    entry_id = row["id"]
    actual_created_at = row["created_at"]

    fresh_row = {
        "id": str(entry_id),
        "attempt_id": str(attempt_id),
        "session_id": str(session_id),
        "stop": row["stop"],
        "error": row["error"],
        "message": row["message"],
        "active": row["active"],
        "mcp": row["mcp"],
        "generated": True,
        "created_at": actual_created_at.isoformat(),
    }
    await write_back_row(
        redis,
        "attempt_completion",
        entry_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )
    # Parent attempt's MV ``is_completed`` flag flips.
    await invalidate_row(redis, "attempt", attempt_id)

    return CreateAttemptCompletionResponse(id=entry_id, active=row["active"])
