"""Attempt strength search — filtered/paginated query against attempt_strength_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_strength.types import (
    GetAttemptStrengthResponse,
)
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "attempt_strength_mv"


async def search_attempt_strengths(
    conn: asyncpg.Connection,
    redis: Redis,
    message_ids: list[UUID] | None = None,
    grade_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetAttemptStrengthResponse]:
    """Search attempt_strength entries from attempt_strength_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT strength_id, message_id, grade_id, name, description, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR message_id = ANY($1))
          AND ($2::uuid[] IS NULL OR grade_id = ANY($2))
        ORDER BY created_at DESC
        LIMIT $3 OFFSET $4
        """,
        message_ids,
        grade_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "strength_id": str(r["strength_id"]),
            "message_id": str(r["message_id"]) if r["message_id"] else None,
            "grade_id": str(r["grade_id"]) if r["grade_id"] else None,
            "name": r["name"],
            "description": r["description"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]

    message_ids_str = {str(m) for m in message_ids} if message_ids else None
    grade_ids_str = {str(g) for g in grade_ids} if grade_ids else None

    def matches(row: dict) -> bool:
        if message_ids_str is not None and str(row.get("message_id")) not in message_ids_str:
            return False
        if grade_ids_str is not None and str(row.get("grade_id")) not in grade_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "attempt_strength",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        id_key="strength_id",
        bypass_cache=bypass_cache,
    )
    return [GetAttemptStrengthResponse.model_validate(r) for r in merged]
