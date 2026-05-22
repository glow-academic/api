"""Attempt replacement search — filtered/paginated query against attempt_replacement_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_replacement.types import (
    GetAttemptReplacementResponse,
)
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "attempt_replacement_mv"


async def search_attempt_replacements(
    conn: asyncpg.Connection,
    redis: Redis,
    improvement_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetAttemptReplacementResponse]:
    """Search attempt_replacement entries from attempt_replacement_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT replacement_id, improvement_id, section, replace AS replace_text, idx, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR improvement_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        improvement_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "replacement_id": str(r["replacement_id"]),
            "improvement_id": str(r["improvement_id"]) if r["improvement_id"] else None,
            "section": r["section"],
            "replace_text": r["replace_text"],
            "idx": r["idx"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]

    improvement_ids_str = {str(x) for x in improvement_ids} if improvement_ids else None

    def matches(row: dict) -> bool:
        if improvement_ids_str is not None and str(row.get("improvement_id")) not in improvement_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "attempt_replacement",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        id_key="replacement_id",
        bypass_cache=bypass_cache,
    )
    return [GetAttemptReplacementResponse.model_validate(r) for r in merged]
