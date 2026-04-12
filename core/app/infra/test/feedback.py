"""Test feedback — infra function for AI grading agent.

Creates a test_feedback entry for a specific tool call against a rubric standard.
Called by the grading agent via the tool execution pipeline.

Flow:
  1. Create feedback entry (grade_id, tool_call_id, score, feedback text)
  2. Refresh MV
  3. Return feedback_id
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.test_feedback.create import create_test_feedback
from app.tools.entries.test_feedback.refresh import refresh_test_feedback
from app.tools.entries.calls.create import create_call
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_feedback_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    grade_id: UUID | None = None,
    tool_call_id: UUID | None = None,
    score: int = 0,
    feedback: str = "",
    total_points: int = 0,
    pass_points: int = 0,
    group_id: UUID | None = None,
    run_id: UUID | None = None,
    **kwargs: str,
) -> dict:
    """Create a test feedback entry for one rubric criterion.

    Accepts kwargs from the AI tool execution path.
    """
    # Coerce from kwargs if not provided directly
    if grade_id is None and "grade_id" in kwargs:
        grade_id = UUID(kwargs["grade_id"])
    if tool_call_id is None and "tool_call_id" in kwargs:
        tool_call_id = UUID(kwargs["tool_call_id"])
    if isinstance(score, str):
        score = int(score)
    if isinstance(total_points, str):
        total_points = int(total_points)
    if isinstance(pass_points, str):
        pass_points = int(pass_points)
    if not feedback and "feedback" in kwargs:
        feedback = kwargs["feedback"]

    if not grade_id:
        raise ValueError("grade_id is required")
    if not tool_call_id:
        raise ValueError("tool_call_id is required")

    async with pool.acquire() as conn:
        # Create a call for audit linkage
        call = await create_call(
            conn,
            run_id=run_id or UUID(int=0),
            session_id=session_id,
        )

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
        "score": score,
    }
