"""Attempt chat bridge CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.attempt_chat_bridge.types import (
    CreateAttemptChatBridgeResponse,
)


async def create_attempt_chat_bridge(
    conn: asyncpg.Connection,
    attempt_id: UUID,
    attempt_chat_id: UUID,
    session_id: UUID,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateAttemptChatBridgeResponse:
    """Create an attempt_chat_bridge_entry row."""
    await conn.execute(
        """
        INSERT INTO attempt_chat_bridge_entry (attempt_id, attempt_chat_id, session_id, active, mcp, generated, created_at)
        VALUES ($1, $2, $3, $4, $5, true, COALESCE($6, NOW()))
        """,
        attempt_id,
        attempt_chat_id,
        session_id,
        not soft,
        mcp,
        created_at,
    )

    return CreateAttemptChatBridgeResponse(
        attempt_id=attempt_id, attempt_chat_id=attempt_chat_id
    )
