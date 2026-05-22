"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_feedback.types import (
    GetAttemptFeedbackResponse,
)
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "attempt_feedback_mv"


async def get_attempt_feedbacks(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_mv: bool = False,
    *,
    bypass_cache: bool = False,
) -> list[GetAttemptFeedbackResponse]:
    """Get attempt_feedback rows by id, aggregated one-row-per-feedback.

    The MV LEFT JOINs feedbacks_standards_connection (fanning out one
    feedback into N rows per linked standard); we collapse the MV result
    via GROUP BY in SQL so the response is one row per feedback with
    ``standard_ids`` as a list. Cache row already stores the aggregate
    shape, so cache and MV slices share the same Pydantic model.
    """
    if not ids:
        return []

    cached_results: dict[str, GetAttemptFeedbackResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for fid in ids:
            cached = await read_back_row(redis, "attempt_feedback", fid)
            if cached is not None:
                cached_results[str(fid)] = (
                    GetAttemptFeedbackResponse.model_validate(cached)
                )
            else:
                missing_ids.append(fid)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetAttemptFeedbackResponse] = {}
    if missing_ids:
        source = await resolve_mv_source(conn, MV_NAME, bypass_mv)
        rows = await conn.fetch(
            f"""
            SELECT feedback_id, grade_id, total, feedback, created_at,
                   COALESCE(
                       ARRAY_AGG(standard_id) FILTER (WHERE standard_id IS NOT NULL),
                       '{{}}'::uuid[]
                   ) AS standard_ids
            FROM {source}
            WHERE feedback_id = ANY($1)
            GROUP BY feedback_id, grade_id, total, feedback, created_at
            """,
            missing_ids,
        )
        for r in rows:
            mv_results[str(r["feedback_id"])] = GetAttemptFeedbackResponse(
                feedback_id=r["feedback_id"],
                grade_id=r["grade_id"],
                standard_ids=list(r["standard_ids"] or []),
                total=r["total"],
                feedback=r["feedback"],
                created_at=r["created_at"],
            )

    out: list[GetAttemptFeedbackResponse] = []
    for fid in ids:
        key = str(fid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
