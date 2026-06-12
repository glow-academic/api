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
from app.infra.test.refresh import refresh_test_impl
from app.infra.server_timing import timed
from app.tools.entries.test_feedback.create import create_test_feedback
from app.tools.entries.test_grade.get import get_test_grades
from app.tools.resources.standard_groups.get import get_standard_groups
from app.tools.resources.standards.search import search_standards
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

    # ── Owner/role/department scope (BOLA + cross-dept guard, T6) ──────────
    # The feedback rows below are keyed on the caller-supplied ``grade_id``.
    # Without this, any authenticated profile could attach forged feedback to
    # ANOTHER user's grade, polluting its grade chain. Resolve
    # ``grade → invocation → owner`` and route through the shared gate
    # (mirrors ``enforce_attempt_access_by_grade``).
    from app.infra.profile_identity_context import resolve_profile_identity_context
    from app.infra.test.permissions import enforce_test_access_by_grade

    requester = await resolve_profile_identity_context(pool, profile_id, redis)
    await enforce_test_access_by_grade(
        pool, redis, grade_id=grade_id, requester=requester,
    )

    with timed("feedback_write"):
      async with pool.acquire() as conn:
        # Step 1: Get standard group → total_points, pass_points + standards.
        # The grader scores at the group level (one tool call → one score
        # for the group). We fan that out at write time into one feedback
        # row per standard in the group so the graded-view path can read
        # per-standard buckets from ``test_feedback_mv`` (mirrors attempt's
        # 1:1 feedback↔standard cardinality, which keeps the MV's
        # ``UNIQUE (feedback_id)`` index intact).
        total_points = 0
        pass_points = 0
        sgs = await get_standard_groups(conn, [standard_group_id], redis)
        if sgs:
            total_points = sgs[0].points
            pass_points = sgs[0].pass_points

        standards = await search_standards(
            conn,
            redis,
            standard_group_ids=[standard_group_id],
            limit_count=1000,
        )
        # ``[None]`` lets the loop below still write one ungrouped
        # feedback row when a group has zero standards configured —
        # avoids dropping the grader's signal on misconfigured rubrics.
        standard_ids_to_write: list[UUID | None] = (
            [s.id for s in standards] if standards else [None]
        )

        # Step 2: Derive run_id — prefer context (kwargs), fall back to grade's call
        run_id: UUID | None = None
        if "run_id" in kwargs and kwargs["run_id"]:
            run_id = kwargs["run_id"] if isinstance(kwargs["run_id"], UUID) else UUID(str(kwargs["run_id"]))
        else:
            grades = await get_test_grades(conn, [grade_id], redis)
            if grades and grades[0].call_id:
                calls = await get_calls(conn, [grades[0].call_id], redis)
                if calls:
                    run_id = calls[0].run_id

        if not run_id:
            raise ValueError("Cannot determine run_id for feedback — not in context and not derivable from grade")

        # Step 3: Create call for audit linkage (one call per grader
        # invocation — shared by every fanned-out feedback row).
        call = await create_call(
            conn,
            redis, run_id=run_id,
            session_id=session_id,
        )

        # Step 4: Create feedback — one row per standard in the group.
        # ``standard_ids=[std_id]`` writes the connection row that
        # ``test_feedback_mv`` LEFT JOINs to project ``standard_id``.
        feedback_ids: list[UUID] = []
        for std_id in standard_ids_to_write:
            result = await create_test_feedback(
                conn,
                redis, grade_id=grade_id,
                call_id=call.id,
                tool_call_id=tool_call_id,
                total=score,
                feedback=feedback,
                total_points=total_points,
                pass_points=pass_points,
                standard_ids=[std_id] if std_id is not None else None,
            )
            feedback_ids.append(result.id)

    with timed("refresh"):
        await refresh_test_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            targets=["test_feedback_mv"],
        )

    await invalidate_tags(["test", "tests", "feedbacks"], redis=redis)

    return {
        "success": True,
        "feedback_ids": [str(fid) for fid in feedback_ids],
        # Preserve the legacy single-id field for callers that only read
        # the first; ``feedback_ids`` is the canonical multi-id surface.
        "feedback_id": str(feedback_ids[0]) if feedback_ids else None,
        "grade_id": str(grade_id),
        "tool_call_id": str(tool_call_id),
        "standard_group_id": str(standard_group_id),
        "standard_ids": [
            str(std_id) for std_id in standard_ids_to_write if std_id is not None
        ],
        "score": score,
        "feedback": feedback,
        "total_points": total_points,
        "pass_points": pass_points,
    }
