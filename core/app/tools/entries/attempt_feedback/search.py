"""attempt_feedback/search — filtered/paginated query against attempt_feedback_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_feedback.types import (
    GetAttemptFeedbackResponse,
)

MV_NAME = "attempt_feedback_mv"


async def search_attempt_feedback_entries(
    conn: asyncpg.Connection,
    redis: Redis,
    grade_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[GetAttemptFeedbackResponse]:
    """Search attempt feedback entries from attempt_feedback_mv with declarative filters.

    # Pattern C infeasible: the MV LEFT JOINs feedbacks_standards_connection,
    # so a single feedback_id produces N rows (one per linked standard) in the
    # result set. hedged_search dedupes by id_key — there's no single id_key
    # that yields a stable one-row-per-cached-entry view that can merge with
    # the MV's fan-out shape without silently dropping (N-1) MV rows behind
    # one cache row. Callers (rubric/export, attempt/context, dashboard/context)
    # depend on the per-standard fan-out (they bucket feedback by standard_id),
    # so restructuring to GROUP BY feedback_id + ARRAY_AGG(standard_id) would
    # break the caller contract. We keep search MV-only; create.py still writes
    # back the aggregate cache row for use by get.py (Pattern B).
    """
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT feedback_id, grade_id, standard_id, total, feedback, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR grade_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        grade_ids,
        limit,
        offset,
    )

    return [GetAttemptFeedbackResponse(**dict(r)) for r in rows]
