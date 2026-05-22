"""Attempt completion search — filtered/paginated query against attempt_completion_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_completion.types import (
    GetAttemptCompletionResponse,
)
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "attempt_completion_mv"


async def search_attempt_completions(
    conn: asyncpg.Connection,
    redis: Redis,
    attempt_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetAttemptCompletionResponse]:
    """Search attempt_completion entries from attempt_completion_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, attempt_id, stop, error, message, session_id, created_at, active, generated, mcp
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR attempt_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        attempt_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": str(r["id"]),
            "attempt_id": str(r["attempt_id"]) if r["attempt_id"] else None,
            "stop": r["stop"],
            "error": r["error"],
            "message": r["message"],
            "session_id": str(r["session_id"]) if r["session_id"] else None,
            "created_at": r["created_at"],
            "active": r["active"],
            "generated": r["generated"],
            "mcp": r["mcp"],
        }
        for r in rows
    ]

    attempt_ids_str = {str(a) for a in attempt_ids} if attempt_ids else None

    def matches(row: dict) -> bool:
        if attempt_ids_str is not None and str(row.get("attempt_id")) not in attempt_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "attempt_completion",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetAttemptCompletionResponse.model_validate(r) for r in merged]
