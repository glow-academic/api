"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.attempt_chat_bridge.types import (
    GetAttemptChatBridgeResponse,
)

MV_NAME = "attempt_chat_bridge_mv"


async def get_attempt_chat_bridge(
    conn: asyncpg.Connection,
    attempt_ids: list[UUID],
) -> list[GetAttemptChatBridgeResponse]:
    """Get attempt_chat_bridge entries by attempt_id from MV."""
    if not attempt_ids:
        return []
    rows = await conn.fetch(
        f"SELECT * FROM {MV_NAME} WHERE attempt_id = ANY($1)", attempt_ids
    )
    return [GetAttemptChatBridgeResponse(**dict(r)) for r in rows]
