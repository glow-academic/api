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


def _fan_out_cached(cached: dict) -> list[GetAttemptFeedbackResponse]:
    """Expand a cached aggregate row into N MV-shape rows (one per standard).

    The cache stores ``standard_ids: list[str]`` (the aggregate of linked
    standards at write-time). The MV LEFT JOINs feedbacks_standards_connection
    so each feedback fans out to N rows (one per linked standard); rows with
    no linked standards still produce one row with ``standard_id=None``.
    This helper mirrors that shape so callers get an identical view from
    cache vs MV.
    """
    base = {
        "feedback_id": cached["feedback_id"],
        "grade_id": cached["grade_id"],
        "total": cached["total"],
        "feedback": cached["feedback"],
        "created_at": cached["created_at"],
    }
    sids = cached.get("standard_ids") or []
    if not sids:
        return [GetAttemptFeedbackResponse(**base, standard_id=None)]
    return [
        GetAttemptFeedbackResponse(**base, standard_id=sid) for sid in sids
    ]


async def get_attempt_feedbacks(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_mv: bool = False,
    *,
    bypass_cache: bool = False,
) -> list[GetAttemptFeedbackResponse]:
    """Get attempt_feedback rows by id (MV-shape: one row per (feedback, standard)).

    Hedged read: per-id cache check first, MV fall-through on miss. Cache rows
    store the aggregate ``standard_ids`` list; we fan out client-side so the
    response matches the MV's LEFT JOIN shape.
    """
    if not ids:
        return []

    out: list[GetAttemptFeedbackResponse] = []
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for fid in ids:
            cached = await read_back_row(redis, "attempt_feedback", fid)
            if cached is not None:
                out.extend(_fan_out_cached(cached))
            else:
                missing_ids.append(fid)
    else:
        missing_ids = list(ids)

    if missing_ids:
        source = await resolve_mv_source(conn, MV_NAME, bypass_mv)
        rows = await conn.fetch(
            f"SELECT * FROM {source} WHERE feedback_id = ANY($1)", missing_ids
        )
        out.extend(GetAttemptFeedbackResponse(**dict(r)) for r in rows)

    return out
