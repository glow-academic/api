"""attempt_feedback/search — filtered/paginated query against attempt_feedback_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_feedback.types import (
    GetAttemptFeedbackResponse,
)
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "attempt_feedback_mv"


async def search_attempt_feedback_entries(
    conn: asyncpg.Connection,
    redis: Redis,
    grade_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetAttemptFeedbackResponse]:
    """Search attempt feedback entries from attempt_feedback_mv.

    The MV ``LEFT JOIN feedbacks_standards_connection`` fans out one
    feedback into N rows per linked standard. We collapse via
    ``GROUP BY feedback_id + ARRAY_AGG(standard_id)`` so the response is
    one row per feedback with ``standard_ids`` as a list. The cache row
    already stores the aggregate, so hedged_search merges naturally
    without violating its one-row-per-id invariant.
    """
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT feedback_id, grade_id, total, feedback, created_at,
               COALESCE(
                   ARRAY_AGG(standard_id) FILTER (WHERE standard_id IS NOT NULL),
                   '{{}}'::uuid[]
               ) AS standard_ids
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR grade_id = ANY($1))
        GROUP BY feedback_id, grade_id, total, feedback, created_at
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        grade_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "feedback_id": str(r["feedback_id"]),
            "grade_id": str(r["grade_id"]) if r["grade_id"] else None,
            "standard_ids": [str(s) for s in (r["standard_ids"] or [])],
            "total": r["total"],
            "feedback": r["feedback"],
            "created_at": r["created_at"],
            "id": str(r["feedback_id"]),
        }
        for r in rows
    ]

    grade_ids_str = {str(g) for g in grade_ids} if grade_ids else None

    def matches(row: dict) -> bool:
        if grade_ids_str is not None and str(row.get("grade_id")) not in grade_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "attempt_feedback",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        id_key="feedback_id",
        bypass_cache=bypass_cache,
    )
    return [GetAttemptFeedbackResponse.model_validate(r) for r in merged]
