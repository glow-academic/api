"""Attempt chat bridge CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.attempt_chat_bridge.types import (
    CreateAttemptChatBridgeResponse,
)
from app.utils.cache.hedged_row import invalidate_row, write_back_row


async def create_attempt_chat_bridge(
    conn: asyncpg.Connection,
    redis: Redis,
    attempt_id: UUID,
    attempt_chat_id: UUID,
    session_id: UUID,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateAttemptChatBridgeResponse:
    """Create an attempt_chat_bridge_entry row."""
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_chat_bridge_entry (attempt_id, attempt_chat_id, session_id, active, mcp, generated, created_at)
        VALUES ($1, $2, $3, $4, $5, true, COALESCE($6, NOW()))
        RETURNING created_at
        """,
        attempt_id,
        attempt_chat_id,
        session_id,
        not soft,
        mcp,
        created_at,
    )
    actual_created_at = row["created_at"] if row else created_at

    # Composite-key bridge: synthesize ``bridge_key`` from
    # (attempt_id, attempt_chat_id) for the per-id cache slot. search.py uses
    # ``id_key="bridge_key"`` to dedupe.
    bridge_key = f"{attempt_id}:{attempt_chat_id}"
    fresh_row = {
        "bridge_key": bridge_key,
        "attempt_id": str(attempt_id),
        "attempt_chat_id": str(attempt_chat_id),
        "created_at": actual_created_at.isoformat() if actual_created_at else None,
        "active": not soft,
        "generated": True,
        "mcp": mcp,
        "session_id": str(session_id),
    }
    if actual_created_at is not None:
        await write_back_row(
            redis,
            "attempt_chat_bridge",
            bridge_key,
            fresh_row,
            score_ms=int(actual_created_at.timestamp() * 1000),
        )
    # Parent attempt's cached attempt_chat_id / chat_entry_id / scenario_ids
    # derive from this bridge; invalidate so the next read picks up MV.
    await invalidate_row(redis, "attempt", attempt_id)
    # The attempt_chat cache row written at attempt_chat/create time has
    # attempt_id=None — this bridge is what links the attempt, so the MV will
    # now hydrate it. Evict the stale attempt_chat cache slot (keyed by the
    # attempt_chat_entry id) so the next get/search falls through to the
    # hydrated MV instead of returning the stale None (see #62).
    await invalidate_row(redis, "attempt_chat", attempt_chat_id)

    return CreateAttemptChatBridgeResponse(
        attempt_id=attempt_id, attempt_chat_id=attempt_chat_id
    )
