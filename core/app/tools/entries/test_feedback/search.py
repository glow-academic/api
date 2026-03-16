"""test_feedback/search — filtered/paginated query against test_feedback_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.test_feedback.types import GetTestFeedbackResponse

MV_NAME = "test_feedback_mv"


async def search_test_feedback_entries(
    conn: asyncpg.Connection,
    grade_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetTestFeedbackResponse]:
    """Search test_feedback entries from test_feedback_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT feedback_id, grade_id, total, feedback, total_points, pass_points, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR grade_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        grade_ids,
        limit,
        offset,
    )

    return [
        GetTestFeedbackResponse(
            feedback_id=r["feedback_id"],
            grade_id=r["grade_id"],
            total=r["total"],
            feedback=r["feedback"],
            total_points=r["total_points"],
            pass_points=r["pass_points"],
            created_at=r["created_at"],
        )
        for r in rows
    ]
