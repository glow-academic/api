"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.test_invocation_completion.types import (
    CreateTestInvocationCompletionResponse,
)
from app.utils.cache.hedged_row import invalidate_row, write_back_row


async def create_test_invocation_completion(
    conn: asyncpg.Connection,
    redis: Redis,
    invocation_id: UUID,
    call_id: UUID,
    *,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
    soft: bool = False,
) -> CreateTestInvocationCompletionResponse:
    """Create a test_invocation_completion entry.

    ``UNIQUE(invocation_id)`` means at most one completion row per invocation. A
    *soft* proposal (``active=false``) is MV-invisible but occupies the unique
    slot. A naive ``ON CONFLICT DO NOTHING`` would wedge the invocation (C1-B,
    mirroring the attempt_completion #339 B1 fix): a later hard complete collides
    with the dormant proposal and no-ops.

    Fix: a hard completion supersedes a DORMANT proposal via
    ``ON CONFLICT DO UPDATE SET active=true`` only when incoming is hard and the
    existing row is dormant. An accepted completion is never clobbered, a soft
    proposal never downgrades, and a duplicate hard completion is idempotent (no
    2nd active row). The returned ``active`` reflects TRUE state.
    """
    incoming_active = not soft
    row = await conn.fetchrow(
        """
        INSERT INTO test_invocation_completion_entry (id, invocation_id, call_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        ON CONFLICT (invocation_id) DO UPDATE
            SET active = true,
                call_id = EXCLUDED.call_id,
                stop = EXCLUDED.stop,
                error = EXCLUDED.error,
                message = EXCLUDED.message,
                mcp = EXCLUDED.mcp
            WHERE test_invocation_completion_entry.active = false
              AND EXCLUDED.active = true
        RETURNING id, created_at, active, stop, error, message, mcp, call_id
        """,
        invocation_id,
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
        # or the existing row is already an accepted completion. Return the
        # row's TRUE current state; the parent MV is already consistent so no
        # cache bust is needed.
        existing = await conn.fetchrow(
            "SELECT id, active FROM test_invocation_completion_entry WHERE invocation_id = $1",
            invocation_id,
        )
        return CreateTestInvocationCompletionResponse(
            id=existing["id"], active=existing["active"]
        )

    entry_id = row["id"]
    created_at = row["created_at"]

    fresh_row = {
        "id": str(entry_id),
        "created_at": created_at.isoformat(),
        "generated": True,
        "mcp": row["mcp"],
        "active": row["active"],
        "invocation_id": str(invocation_id),
        "stop": row["stop"],
        "error": row["error"],
        "message": row["message"],
        "call_id": str(row["call_id"]),
    }
    await write_back_row(
        redis,
        "test_invocation_completion",
        entry_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )
    # Bust the parent test_invocation write-back row: its cached
    # ``invocation_completed`` was written False at create-time and this
    # completion flips the MV-derived value to True. Without this, a cached
    # parent GET shadows the hydrated MV with stale False until TTL (#98).
    await invalidate_row(redis, "test_invocation", invocation_id)

    return CreateTestInvocationCompletionResponse(id=entry_id, active=row["active"])
