"""Test feedback — infra function for AI grading agent.

Creates a test_feedback entry for a specific tool call against a rubric standard group.
Derives run_id from grade, and total_points/pass_points from standard group.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.calls.create import create_call
from app.tools.entries.calls.get import get_calls
from app.tools.entries.test_feedback.create import create_test_feedback
from app.tools.entries.test_feedback.refresh import refresh_test_feedback
from app.tools.entries.test_grade.get import get_test_grades
from app.tools.resources.standard_groups.get import get_standard_groups
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_feedback_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    grade_id: UUID | None = None,
    tool_call_id: UUID | None = None,
    standard_group_id: UUID | None = None,
    score: int = 0,
    feedback: str = "",
    **kwargs: Any,
) -> dict:
    """Create a test feedback entry for one rubric criterion.

    Model passes: grade_id, tool_call_id, standard_group_id, score, feedback.
    Infra derives: total_points/pass_points from standard group, run_id from grade.
    """
    if grade_id is None and "grade_id" in kwargs:
        grade_id = UUID(kwargs["grade_id"])
    if tool_call_id is None and "tool_call_id" in kwargs:
        tool_call_id = UUID(kwargs["tool_call_id"])
    if standard_group_id is None and "standard_group_id" in kwargs:
        standard_group_id = UUID(kwargs["standard_group_id"])
    if isinstance(score, str):
        score = int(score)
    if not feedback and "feedback" in kwargs:
        feedback = kwargs["feedback"]

    if not grade_id:
        raise ValueError("grade_id is required")
    if not tool_call_id:
        raise ValueError("tool_call_id is required")
    if not standard_group_id:
        raise ValueError("standard_group_id is required")

    async with pool.acquire() as conn:
        # Step 1: Get standard group → total_points, pass_points
        total_points = 0
        pass_points = 0
        sgs = await get_standard_groups(conn, [standard_group_id], redis)
        if sgs:
            total_points = sgs[0].points
            pass_points = sgs[0].pass_points

        # Step 2: Derive run_id — prefer context (kwargs), fall back to grade's call
        run_id: UUID | None = None
        if "run_id" in kwargs and kwargs["run_id"]:
            run_id = kwargs["run_id"] if isinstance(kwargs["run_id"], UUID) else UUID(str(kwargs["run_id"]))
        else:
            grades = await get_test_grades(conn, ids=[grade_id])
            if grades and grades[0].call_id:
                calls = await get_calls(conn, [grades[0].call_id])
                if calls:
                    run_id = calls[0].run_id

        if not run_id:
            raise ValueError("Cannot determine run_id for feedback — not in context and not derivable from grade")

        # Step 3: Create call for audit linkage
        call = await create_call(
            conn,
            run_id=run_id,
            session_id=session_id,
        )

        # Step 4: Create feedback
        result = await create_test_feedback(
            conn,
            grade_id=grade_id,
            call_id=call.id,
            tool_call_id=tool_call_id,
            total=score,
            feedback=feedback,
            total_points=total_points,
            pass_points=pass_points,
        )

        await refresh_test_feedback(conn)

    await invalidate_tags(["test", "tests", "feedbacks"], redis=redis)

    return {
        "success": True,
        "feedback_id": str(result.id),
        "grade_id": str(grade_id),
        "tool_call_id": str(tool_call_id),
        "standard_group_id": str(standard_group_id),
        "score": score,
        "feedback": feedback,
        "total_points": total_points,
        "pass_points": pass_points,
    }
