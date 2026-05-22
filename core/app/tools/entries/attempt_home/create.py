"""Attempt home CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.attempt_home.types import CreateAttemptHomeResponse
from app.utils.cache.hedged_row import write_back_row


async def create_attempt_home(
    conn: asyncpg.Connection,
    redis: Redis,
    attempt_id: UUID,
    home_id: UUID,
    session_id: UUID,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateAttemptHomeResponse:
    """Create an attempt_home_entry bridge row."""
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_home_entry (attempt_id, home_id, session_id, active, mcp, generated, created_at)
        VALUES ($1, $2, $3, $4, $5, true, COALESCE($6, NOW()))
        RETURNING created_at
        """,
        attempt_id,
        home_id,
        session_id,
        not soft,
        mcp,
        created_at,
    )
    actual_created_at = row["created_at"] if row else created_at

    # Composite-key bridge (no singular id): synthesize ``home_link_key``
    # from (attempt_id, home_id) for the per-id cache slot. search.py uses
    # ``id_key="home_link_key"`` to dedupe against MV rows.
    home_link_key = f"{attempt_id}:{home_id}"
    fresh_row = {
        "home_link_key": home_link_key,
        "attempt_id": str(attempt_id),
        "home_id": str(home_id),
        "created_at": actual_created_at.isoformat() if actual_created_at else None,
        "active": not soft,
        "generated": True,
        "mcp": mcp,
        "session_id": str(session_id),
    }
    if actual_created_at is not None:
        await write_back_row(
            redis,
            "attempt_home",
            home_link_key,
            fresh_row,
            score_ms=int(actual_created_at.timestamp() * 1000),
        )

    return CreateAttemptHomeResponse(attempt_id=attempt_id, home_id=home_id)
