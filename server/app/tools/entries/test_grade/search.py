"""Test grade search — filtered/paginated query against test_grade_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.test_grade.types import GetTestGradeResponse

MV_NAME = "test_grade_mv"


async def search_test_grades(
    conn: asyncpg.Connection,
    invocation_ids: list[UUID] | None = None,
    run_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetTestGradeResponse]:
    """Search test_grade entries from test_grade_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, invocation_id, run_id, created_at, updated_at,
               passed, score, time_taken, generated, mcp, active, call_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR invocation_id = ANY($1))
          AND ($2::uuid[] IS NULL OR run_id = ANY($2))
        ORDER BY created_at DESC
        LIMIT $3 OFFSET $4
        """,
        invocation_ids,
        run_ids,
        limit,
        offset,
    )

    return [GetTestGradeResponse(**dict(r)) for r in rows]
