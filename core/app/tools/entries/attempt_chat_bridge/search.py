"""Attempt chat bridge search — filtered/paginated query against attempt_chat_bridge_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_chat_bridge.types import (
    GetAttemptChatBridgeResponse,
)

MV_NAME = "attempt_chat_bridge_mv"


async def search_attempt_chat_bridges(
    conn: asyncpg.Connection,
    attempt_ids: list[UUID] | None = None,
    attempt_chat_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
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
        limit,
        offset,
    )

    return [GetAttemptChatBridgeResponse(**dict(r)) for r in rows]
