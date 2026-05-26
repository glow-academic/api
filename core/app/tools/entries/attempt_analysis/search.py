"""Attempt analysis search — filtered/paginated query against attempt_analysis_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_analysis.types import (
    GetAttemptAnalysisResponse,
)
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "attempt_analysis_mv"


async def search_attempt_analyses(
    conn: asyncpg.Connection,
    redis: Redis,
    grade_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetAttemptAnalysisResponse]:
    """Search attempt_analysis entries from attempt_analysis_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT analysis_id, grade_id, content, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR grade_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        grade_ids,
        limit + offset + 1000,
        0,
    )
    mv_dicts = [dict(r) for r in rows]

    grade_ids_str = {str(g) for g in grade_ids} if grade_ids else None

    def matches(row: dict) -> bool:
        if grade_ids_str is not None and str(row.get("grade_id")) not in grade_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "attempt_analysis",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        id_key="analysis_id",
        bypass_cache=bypass_cache,
    )
    return [GetAttemptAnalysisResponse.model_validate(r) for r in merged]
