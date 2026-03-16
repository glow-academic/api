"""Attempt grade search — filtered/paginated query against attempt_grade_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_grade.types import GetAttemptGradeResponse

MV_NAME = "attempt_grade_mv"


async def search_attempt_grades(
    conn: asyncpg.Connection,
    chat_ids: list[UUID] | None = None,
    rubric_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetAttemptGradeResponse]:
    """Search attempt_grade entries from attempt_grade_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT grade_id, chat_id, score, passed, time_taken, total_points,
               pass_points, rubric_id, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR chat_id = ANY($1))
          AND ($2::uuid[] IS NULL OR rubric_id = ANY($2))
        ORDER BY created_at DESC
        LIMIT $3 OFFSET $4
        """,
        chat_ids,
        rubric_ids,
        limit,
        offset,
    )

    return [GetAttemptGradeResponse(**dict(r)) for r in rows]
