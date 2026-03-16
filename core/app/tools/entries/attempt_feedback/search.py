"""attempt_feedback/search — filtered/paginated query against attempt_feedback_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_feedback.types import (
    GetAttemptFeedbackResponse,
)

MV_NAME = "attempt_feedback_mv"


async def search_attempt_feedback_entries(
    conn: asyncpg.Connection,
    grade_ids: list[UUID] | None = None,
    standard_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetAttemptFeedbackResponse]:
    """Search attempt feedback entries from attempt_feedback_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT feedback_id, grade_id, standard_id, total, feedback, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR grade_id = ANY($1))
          AND ($2::uuid[] IS NULL OR standard_id = ANY($2))
        ORDER BY created_at DESC
        LIMIT $3 OFFSET $4
        """,
        grade_ids,
        standard_ids,
        limit,
        offset,
    )

    return [GetAttemptFeedbackResponse(**dict(r)) for r in rows]
