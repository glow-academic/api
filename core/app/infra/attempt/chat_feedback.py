"""Attempt chat feedback — thin infra impl for generate pipeline.

Model passes: grade_id, standard_id, feedback.
Infra derives: score (standard points), total (standard group max points).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.attempt_feedback.create import create_attempt_feedback
from app.tools.entries.attempt_feedback.refresh import refresh_attempt_feedback
from app.tools.resources.standards.get import get_standards
from app.tools.resources.standard_groups.get import get_standard_groups


async def chat_feedback_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    grade_id: UUID | None = None,
    standard_id: UUID | None = None,
    feedback: str = "",
    **kwargs: Any,
):
    """Create feedback for a grade by selecting a rubric standard.

    Model passes: grade_id, standard_id (which rubric level), feedback.
    Infra derives: score (standard points), total (group max points).
    """
    if grade_id is None and "grade_id" in kwargs:
        grade_id = UUID(kwargs["grade_id"])
    if standard_id is None and "standard_id" in kwargs:
        standard_id = UUID(kwargs["standard_id"])
    if isinstance(grade_id, str):
        grade_id = UUID(grade_id)
    if isinstance(standard_id, str):
        standard_id = UUID(standard_id)
    if not feedback and "feedback" in kwargs:
        feedback = str(kwargs["feedback"])

    if not grade_id:
        raise ValueError("grade_id is required")
    if not standard_id:
        raise ValueError(
            "standard_id is required. Pick the rubric standard that best matches "
            "the trainee's performance from the Rubric section."
        )

    # Resolve score from standard, total from standard group
    standards = await get_standards(pool, [standard_id], redis)
    if not standards:
        raise ValueError(f"Standard {standard_id} not found")
    standard = standards[0]
    score = standard.points or 0

    total = score
    if standard.standard_group_id:
        sgs = await get_standard_groups(pool, [standard.standard_group_id], redis)
        if sgs:
            total = sgs[0].points or score

    async with pool.acquire() as conn:
        result = await create_attempt_feedback(
            conn,
            grade_id=grade_id,
            session_id=session_id,
            total=total,
            feedback=feedback or "No feedback provided",
            standard_ids=[standard_id],
        )

    async with pool.acquire() as conn:
        await refresh_attempt_feedback(conn)

    return {
        "feedback_id": str(result.id),
        "grade_id": str(grade_id),
        "standard_id": str(standard_id),
        "score": score,
        "total": total,
    }
