"""Test grade — infra function for AI grading agent.

Creates a test_grade entry for a test invocation.
Called by the grading agent via the tool execution pipeline.

Flow:
  1. Create grade entry (invocation_id, passed, score, time_taken)
  2. Refresh MV
  3. Return grade_id for subsequent feedback calls
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.test_grade.create import create_test_grade
from app.tools.entries.test_grade.refresh import refresh_test_grade
from app.tools.entries.calls.create import create_call
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_grade_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    invocation_id: UUID | None = None,
    run_id: UUID | None = None,
    passed: bool = False,
    score: int = 0,
    time_taken: int = 0,
    group_id: UUID | None = None,
    **kwargs: str,
) -> dict:
    """Create a test grade entry.

    Accepts kwargs from the AI tool execution path.
    """
    # Coerce from kwargs if not provided directly
    if invocation_id is None and "invocation_id" in kwargs:
        invocation_id = UUID(kwargs["invocation_id"])
    if run_id is None and "run_id" in kwargs:
        run_id = UUID(kwargs["run_id"])
    if isinstance(passed, str):
        passed = passed.lower() in ("true", "1", "yes")
    if isinstance(score, str):
        score = int(score)
    if isinstance(time_taken, str):
        time_taken = int(time_taken)

    if not invocation_id:
        raise ValueError("invocation_id is required")

    async with pool.acquire() as conn:
        # Create a call for audit linkage
        call = await create_call(
            conn,
            run_id=run_id or UUID(int=0),
            session_id=session_id,
        )

        result = await create_test_grade(
            conn,
            invocation_id=invocation_id,
            call_id=call.id,
            run_id=run_id or UUID(int=0),
            time_taken=time_taken,
            passed=passed,
            score=score,
        )

        await refresh_test_grade(conn)

    await invalidate_tags(["test", "tests", "grades"], redis=redis)

    return {
        "success": True,
        "grade_id": str(result.id),
        "invocation_id": str(invocation_id),
        "passed": passed,
        "score": score,
    }
