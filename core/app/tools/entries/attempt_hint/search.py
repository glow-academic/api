"""Attempt hint search — filtered/paginated query against attempt_hint_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_hint.types import GetAttemptHintResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "attempt_hint_mv"


async def search_attempt_hints(
    conn: asyncpg.Connection,
    redis: Redis,
    message_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetAttemptHintResponse]:
    """Search attempt hints from attempt_hint_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT hint_id, message_id, hint, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR message_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        message_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "hint_id": str(r["hint_id"]),
            "message_id": str(r["message_id"]) if r["message_id"] else None,
            "hint": r["hint"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]

    message_ids_str = {str(m) for m in message_ids} if message_ids else None

    def matches(row: dict) -> bool:
        if message_ids_str is not None and str(row.get("message_id")) not in message_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "attempt_hint",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        id_key="hint_id",
        bypass_cache=bypass_cache,
    )
    return [GetAttemptHintResponse.model_validate(r) for r in merged]
