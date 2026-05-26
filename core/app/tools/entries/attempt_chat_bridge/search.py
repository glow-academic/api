"""Attempt chat bridge search — filtered/paginated query against attempt_chat_bridge_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_chat_bridge.types import (
    GetAttemptChatBridgeResponse,
)
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "attempt_chat_bridge_mv"


async def search_attempt_chat_bridges(
    conn: asyncpg.Connection,
    redis: Redis,
    attempt_ids: list[UUID] | None = None,
    attempt_chat_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetAttemptChatBridgeResponse]:
    """Search attempt_chat_bridge entries from attempt_chat_bridge_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT attempt_id, attempt_chat_id, created_at, active, generated, mcp, session_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR attempt_id = ANY($1))
          AND ($2::uuid[] IS NULL OR attempt_chat_id = ANY($2))
        ORDER BY created_at DESC
        LIMIT $3 OFFSET $4
        """,
        attempt_ids,
        attempt_chat_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "bridge_key": f"{r['attempt_id']}:{r['attempt_chat_id']}",
            "attempt_id": str(r["attempt_id"]),
            "attempt_chat_id": str(r["attempt_chat_id"]),
            "created_at": r["created_at"],
            "active": r["active"],
            "generated": r["generated"],
            "mcp": r["mcp"],
            "session_id": str(r["session_id"]) if r["session_id"] else None,
        }
        for r in rows
    ]

    attempt_ids_str = {str(a) for a in attempt_ids} if attempt_ids else None
    attempt_chat_ids_str = (
        {str(c) for c in attempt_chat_ids} if attempt_chat_ids else None
    )

    def matches(row: dict) -> bool:
        if attempt_ids_str is not None and str(row.get("attempt_id")) not in attempt_ids_str:
            return False
        if attempt_chat_ids_str is not None and str(row.get("attempt_chat_id")) not in attempt_chat_ids_str:
            return False
        if not row.get("active", True):
            return False
        return True

    merged = await hedged_search(
        redis,
        "attempt_chat_bridge",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        id_key="bridge_key",
        bypass_cache=bypass_cache,
    )
    return [
        GetAttemptChatBridgeResponse.model_validate(
            {k: v for k, v in r.items() if k != "bridge_key"}
        )
        for r in merged
    ]
