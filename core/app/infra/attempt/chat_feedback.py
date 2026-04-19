"""Attempt chat feedback — thin infra impl for generate pipeline.

Model passes: grade_id, score, feedback, standard_group_id.
Infra derives: total (points for this standard group).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_feedback.create import create_attempt_feedback
from app.tools.entries.attempt_feedback.refresh import refresh_attempt_feedback
from app.tools.resources.standard_groups.get import get_standard_groups


async def chat_feedback_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    grade_id: UUID | None = None,
    score: int = 0,
    feedback: str = "",
    standard_group_id: UUID | None = None,
    standard_ids: list[UUID] | None = None,
    **kwargs: Any,
):
    """Create feedback for a grade.

    Model passes: grade_id, score, feedback, standard_group_id.
    Infra derives: total from standard group points.
    """
    if grade_id is None and "grade_id" in kwargs:
        grade_id = UUID(kwargs["grade_id"])
    if standard_group_id is None and "standard_group_id" in kwargs:
        standard_group_id = UUID(kwargs["standard_group_id"])
    if isinstance(grade_id, str):
        grade_id = UUID(grade_id)
    if isinstance(standard_group_id, str):
        standard_group_id = UUID(standard_group_id)
    if isinstance(score, str):
        score = int(score)
    if not feedback and "feedback" in kwargs:
        feedback = str(kwargs["feedback"])

    if not grade_id:
        raise ValueError("grade_id is required")

    # Derive total from standard group + validate score
    total = score
    resolved_standard_ids = standard_ids
    if standard_group_id:
        async with pool.acquire() as conn:
            sgs = await get_standard_groups(conn, [standard_group_id], redis)
            if sgs:
                total = sgs[0].points or score
                if total > 0 and score > total:
                    raise ValueError(
                        f"Score {score} exceeds maximum of {total} for this standard group. "
                        f"Adjust score to be between 0 and {total}."
                    )
                if score < 0:
                    raise ValueError(
                        f"Score cannot be negative. Valid range: 0–{total}."
                    )
    else:
        raise ValueError(
            "standard_group_id is required. Pass the standard group UUID from the rubric."
        )

    async with pool.acquire() as conn:
        result = await create_attempt_feedback(
            conn,
            grade_id=grade_id,
            session_id=session_id,
            total=total,
            feedback=feedback or "No feedback provided",
            standard_ids=resolved_standard_ids,
        )

    async with pool.acquire() as conn:
        await refresh_attempt_feedback(conn)

    return {
        "feedback_id": str(result.id),
        "grade_id": str(grade_id),
        "score": score,
        "total": total,
    }
