"""Attempt analysis search — filtered/paginated query against attempt_analysis_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_analysis.types import (
    GetAttemptAnalysisResponse,
)

MV_NAME = "attempt_analysis_mv"


async def search_attempt_analyses(
    conn: asyncpg.Connection,
    grade_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
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
        limit,
        offset,
    )

    return [GetAttemptAnalysisResponse(**dict(r)) for r in rows]
