"""Tokens CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.tokens.types import CreateTokenResponse
from app.utils.cache.hedged_row import invalidate_row, write_back_row


async def create_token(
    conn: asyncpg.Connection,
    redis: Redis,
    run_id: UUID,
    session_id: UUID,
    *,
    id: UUID | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_input_tokens: int = 0,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateTokenResponse:
    """Create a tokens entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO tokens_entry (id, run_id, input_tokens, output_tokens, cached_input_tokens, session_id, active, mcp, generated, created_at)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true, COALESCE($9, NOW()))
        RETURNING id, created_at
        """,
        run_id,
        input_tokens,
        output_tokens,
        cached_input_tokens,
        session_id,
        not soft,
        mcp,
        id,
        created_at,
    )

    if row is None:
        raise ValueError("Failed to create tokens entry")

    token_id = row["id"]
    actual_created_at = row["created_at"]

    fresh_row = {
        "id": str(token_id),
        "run_id": str(run_id),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_input_tokens": cached_input_tokens,
        "session_id": str(session_id) if session_id else None,
        "active": not soft,
        "mcp": mcp,
        "generated": True,
        "created_at": actual_created_at.isoformat(),
    }
    await write_back_row(
        redis,
        "tokens",
        token_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )
    # Parent run's cached input/output/cached_input_tokens aggregates are
    # now stale; let the next read pick up the fresh MV value.
    await invalidate_row(redis, "runs", run_id)

    return CreateTokenResponse(id=token_id)
