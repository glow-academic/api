"""Attempt improvement search — filtered/paginated query against attempt_improvement_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_improvement.types import (
    GetAttemptImprovementResponse,
)
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "attempt_improvement_mv"


async def search_attempt_improvements(
    conn: asyncpg.Connection,
    redis: Redis,
    message_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetAttemptImprovementResponse]:
    """Search attempt_improvement entries from attempt_improvement_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT improvement_id, message_id, name, description, created_at
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
            "improvement_id": str(r["improvement_id"]),
            "message_id": str(r["message_id"]) if r["message_id"] else None,
            "name": r["name"],
            "description": r["description"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]

    message_ids_str = {str(m) for m in message_ids} if message_ids else None

    def matches(row: dict) -> bool:
        if (
            message_ids_str is not None
            and str(row.get("message_id")) not in message_ids_str
        ):
            return False
        return True

    merged = await hedged_search(
        redis,
        "attempt_improvement",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        id_key="improvement_id",
        bypass_cache=bypass_cache,
    )
    return [GetAttemptImprovementResponse.model_validate(r) for r in merged]
