"""Entry CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_chat_completion.types import (
    CreateAttemptChatCompletionResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_attempt_chat_completion(
    conn: asyncpg.Connection,
    redis: Redis,
    chat_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateAttemptChatCompletionResponse:
    """Create an attempt_chat_completion entry.

    ``UNIQUE(chat_id)`` means at most one completion row per chat. A *soft*
    proposal (``active=false``) is MV-invisible — the chat still reads "not
    completed" — but it occupies the unique slot. A naive
    ``ON CONFLICT DO NOTHING`` then permanently wedges the chat: a later hard
    complete (``active=true``) collides with the dormant proposal, no-ops, and
    the chat can never reach the completed terminal state (B1).

    Fix: a real (hard) completion *supersedes* a DORMANT proposal —
    ``ON CONFLICT DO UPDATE SET active=true`` but only when the incoming row is
    hard and the existing row is dormant. A legitimately-accepted completion
    (``active=true``) is never clobbered, and a soft proposal never downgrades
    an existing row. The returned ``active`` reflects the row's TRUE state so the
    caller can tell whether the completion actually took effect.
    """
    incoming_active = not soft
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_chat_completion_entry (id, chat_id, session_id, stop, error, message, active, mcp, generated, created_at)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true, COALESCE($9, NOW()))
        ON CONFLICT (chat_id) DO UPDATE
            SET active = true,
                session_id = EXCLUDED.session_id,
                stop = EXCLUDED.stop,
                error = EXCLUDED.error,
                message = EXCLUDED.message,
                mcp = EXCLUDED.mcp,
                created_at = EXCLUDED.created_at
            WHERE attempt_chat_completion_entry.active = false
              AND EXCLUDED.active = true
        RETURNING id, created_at, active, stop, error, message, mcp
        """,
        chat_id,
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
        # Conflict that neither inserted nor superseded: incoming soft proposal,
        # or the existing row is already an accepted (active=true) completion.
        # Return the row's TRUE current state so the caller does not mistake a
        # dormant/unchanged slot for a fresh successful completion.
        existing = await conn.fetchrow(
            "SELECT id, active FROM attempt_chat_completion_entry WHERE chat_id = $1",
            chat_id,
        )
        return CreateAttemptChatCompletionResponse(
            id=existing["id"], active=existing["active"]
        )

    entry_id = row["id"]
    actual_created_at = row["created_at"]

    fresh_row = {
        "id": str(entry_id),
        "chat_id": str(chat_id),
        "stop": row["stop"],
        "error": row["error"],
        "message": row["message"],
        "created_at": actual_created_at.isoformat(),
        "active": row["active"],
        "generated": True,
        "mcp": row["mcp"],
        "session_id": str(session_id) if session_id is not None else None,
    }
    await write_back_row(
        redis,
        "attempt_chat_completion",
        entry_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )

    return CreateAttemptChatCompletionResponse(id=entry_id, active=row["active"])
