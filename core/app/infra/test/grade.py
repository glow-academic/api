"""Test grade — infra function for AI grading agent.

Creates a test_grade entry for a test invocation.
Derives everything from invocation_id via black boxes:
  - group_id from invocation
  - run_id from test → call chain
  - passed from rubric threshold
  - time_taken from timestamps
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.calls.create import create_call
from app.tools.entries.calls.get import get_calls
from app.tools.entries.test.get import get_tests
from app.infra.test.refresh import refresh_test_impl
from app.tools.entries.test_grade.create import create_test_grade
from app.tools.entries.test_invocation.get import get_test_invocations
from app.tools.resources.rubrics.get import get_rubrics
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_grade_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    invocation_id: UUID | None = None,
    score: int = 0,
    full: bool = False,
    **kwargs: object,
) -> dict:
    """Create a test grade entry.

    Model passes: invocation_id, score (or full=True for max marks).
    Infra derives everything else from invocation_id:
      - run_id (test → call → run chain)
      - passed (score vs rubric threshold)
      - time_taken (now - invocation created_at)

    ``full=True`` shortcut — server resolves the rubric and fills in
    ``score = total_points`` so callers don't need to know the max
    ahead of time. Useful for "full marks" workflows where the client
    just wants to promote a candidate without computing the rubric.
    """
    if invocation_id is None and "invocation_id" in kwargs:
        invocation_id = UUID(kwargs["invocation_id"])
    if isinstance(score, str):
        score = int(score)
    if isinstance(full, str):
        full = full.lower() in ("true", "1", "yes")

    if not invocation_id:
        raise ValueError("invocation_id is required")

    async with pool.acquire() as conn:
        # Step 1: Get invocation → rubric_id, test_id, created_at
        invocations = await get_test_invocations(
            conn, [invocation_id], redis,
        )
        if not invocations:
            raise ValueError(f"Invocation {invocation_id} not found")

        inv = invocations[0]
        rubric_id = inv.rubric_id

        # Step 2: Derive run_id — prefer context (kwargs), fall back to test chain
        run_id: UUID | None = None
        if "run_id" in kwargs and kwargs["run_id"]:
            raw_run_id = kwargs["run_id"]
            run_id = raw_run_id if isinstance(raw_run_id, UUID) else UUID(str(raw_run_id))
        elif inv.test_id:
            tests = await get_tests(conn, [inv.test_id], redis)
            if tests and tests[0].call_id:
                calls = await get_calls(conn, [tests[0].call_id], redis)
                if calls:
                    run_id = calls[0].run_id

        # Step 3: Get rubric → raw point bounds and pass threshold
        total_points = 0
        pass_points = 0
        if rubric_id:
            rubrics = await get_rubrics(conn, [rubric_id], redis)
            if rubrics:
                total_points = rubrics[0].total_points or 0
                pass_points = rubrics[0].pass_points

        # ``full=True`` shortcut — fill in max marks now that we know
        # the rubric's total_points. Caller-supplied ``score`` is
        # ignored when ``full`` is set.
        if full:
            score = total_points

        if total_points > 0 and score > total_points:
            raise ValueError(
                f"Score {score} exceeds maximum of {total_points}. "
                f"Pass threshold is {pass_points}."
            )
        if score < 0:
            raise ValueError(
                f"Score cannot be negative. Valid range: 0-{total_points}."
            )

        # Step 4: Derive passed and time_taken
        passed = score >= pass_points if pass_points > 0 else score > 0
        time_taken_ms = int(
            (datetime.now(UTC) - inv.invocation_created_at).total_seconds() * 1000
        )

        # Step 5: Create call for audit linkage
        if not run_id:
            raise ValueError("Cannot determine run_id for grade — not in context and not derivable from test chain")

        call = await create_call(
            conn,
            redis, run_id=run_id,
            session_id=session_id,
        )

        # Step 6: Create grade
        result = await create_test_grade(
            conn,
            redis, invocation_id=invocation_id,
            call_id=call.id,
            time_taken=time_taken_ms,
            passed=passed,
            score=score,
        )

    await refresh_test_impl(
        pool, redis, profile_id=profile_id, session_id=session_id,
        targets=["test_grade_mv"],
    )

    await invalidate_tags(["test", "tests", "grades"], redis=redis)

    return {
        "success": True,
        "grade_id": str(result.id),
        "invocation_id": str(invocation_id),
        "passed": passed,
        "score": score,
        "time_taken": time_taken_ms,
    }
