"""Test invocation bridge CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.sessions.create import create_session
from app.tools.entries.test_invocation_bridge.types import (
    CreateTestInvocationBridgeResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_test_invocation_bridge(
    conn: asyncpg.Connection,
    redis: Redis,
    test_invocation_id: UUID,
    invocation_id: UUID,
    *,
    session_id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateTestInvocationBridgeResponse:
    """Create a test_invocation_bridge_entry bridge row."""
    if session_id is None:
        session = await create_session(conn, redis, mcp=mcp, soft=soft)
        session_id = session.id

    row = await conn.fetchrow(
        """
        INSERT INTO test_invocation_bridge_entry (test_invocation_id, invocation_id, session_id, active, mcp, generated)
        VALUES ($1, $2, $3, $4, $5, true)
        RETURNING created_at
        """,
        test_invocation_id,
        invocation_id,
        session_id,
        not soft,
        mcp,
    )

    created_at = row["created_at"] if row else None

    # Composite-key bridge: use a synthetic id <test_invocation_id>:<invocation_id>
    # for the per-id cache slot. search.py uses id_key="bridge_key" to dedupe
    # against MV rows that share the same composite key.
    bridge_key = f"{test_invocation_id}:{invocation_id}"
    fresh_row = {
        "bridge_key": bridge_key,
        "test_invocation_id": str(test_invocation_id),
        "invocation_id": str(invocation_id),
        "created_at": created_at.isoformat() if created_at else None,
        "active": not soft,
        "generated": True,
        "mcp": mcp,
        "session_id": str(session_id),
    }
    score_ms = int(created_at.timestamp() * 1000) if created_at else None
    await write_back_row(
        redis,
        "test_invocation_bridge",
        bridge_key,
        fresh_row,
        score_ms=score_ms,
    )

    return CreateTestInvocationBridgeResponse(
        test_invocation_id=test_invocation_id, invocation_id=invocation_id
    )
