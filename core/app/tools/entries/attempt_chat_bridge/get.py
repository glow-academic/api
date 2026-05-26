"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_chat_bridge.types import (
    GetAttemptChatBridgeResponse,
)
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "attempt_chat_bridge_mv"


async def get_attempt_chat_bridge(
    conn: asyncpg.Connection,
    attempt_ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetAttemptChatBridgeResponse]:
    """Get attempt_chat_bridge entries by attempt_id (with cache hedge).

    Composite-PK bridge keyed by ``(attempt_id, attempt_chat_id)`` —
    cached as synthetic ``bridge_key``; merged with MV result filtered
    by attempt_id.
    """
    if not attempt_ids:
        return []
    rows = await conn.fetch(
        f"SELECT * FROM {MV_NAME} WHERE attempt_id = ANY($1)", attempt_ids,
    )
    mv_dicts = [
        {
            "bridge_key": f"{r['attempt_id']}:{r['attempt_chat_id']}",
            "attempt_id": str(r["attempt_id"]) if r["attempt_id"] else None,
            "attempt_chat_id": (
                str(r["attempt_chat_id"]) if r["attempt_chat_id"] else None
            ),
            "session_id": str(r["session_id"]) if r.get("session_id") else None,
            "created_at": r["created_at"],
            "active": r.get("active", True),
            "generated": r.get("generated", True),
            "mcp": r.get("mcp", False),
        }
        for r in rows
    ]
    attempt_ids_str = {str(a) for a in attempt_ids}

    def matches(row: dict) -> bool:
        return str(row.get("attempt_id")) in attempt_ids_str

    merged = await hedged_search(
        redis,
        "attempt_chat_bridge",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=10000,
        offset=0,
        id_key="bridge_key",
        bypass_cache=bypass_cache,
    )
    return [GetAttemptChatBridgeResponse.model_validate(r) for r in merged]
