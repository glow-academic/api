"""Test invocation bridge CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.sessions.create import create_session
from app.tools.entries.test_invocation_bridge.types import (
    CreateTestInvocationBridgeResponse,
)


async def create_test_invocation_bridge(
    conn: asyncpg.Connection,
    test_invocation_id: UUID,
    invocation_id: UUID,
    *,
    session_id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateTestInvocationBridgeResponse:
    """Create a test_invocation_bridge_entry bridge row."""
    if session_id is None:
        session = await create_session(conn, mcp=mcp, soft=soft)
        session_id = session.id

    await conn.execute(
        """
        INSERT INTO test_invocation_bridge_entry (test_invocation_id, invocation_id, session_id, active, mcp, generated)
        VALUES ($1, $2, $3, $4, $5, true)
        """,
        test_invocation_id,
        invocation_id,
        session_id,
        not soft,
        mcp,
    )

    return CreateTestInvocationBridgeResponse(
        test_invocation_id=test_invocation_id, invocation_id=invocation_id
    )
