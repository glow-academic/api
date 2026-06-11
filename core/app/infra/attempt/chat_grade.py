"""Attempt chat grade — thin infra impl for generate pipeline.

Model passes: chat_id, score.
Infra derives: passed (from rubric threshold), time_taken (from timestamps).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.attempt.permissions import check_attempt_access
from app.infra.attempt.refresh import refresh_attempt_impl
from app.infra.dashboard.visibility import is_profile_in_department_scope
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.entries.attempt_chat.search import search_attempt_chats
from app.tools.entries.attempt_grade.create import create_attempt_grade
from app.tools.resources.rubrics.get import get_rubrics


async def chat_grade_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    chat_id: UUID | None = None,
    score: int = 0,
    **kwargs: Any,
):
    """Create a grade for an attempt chat.

    Model passes: chat_id, score.
    Infra derives: passed, time_taken.
    """
    if chat_id is None and "chat_id" in kwargs:
        chat_id = UUID(kwargs["chat_id"])
    if isinstance(score, str):
        score = int(score)
    if isinstance(chat_id, str):
        chat_id = UUID(chat_id)

    if not chat_id:
        raise ValueError("chat_id is required")

    # Step 1: Get chat → rubric, created_at
    with timed("db_read"):
        async with pool.acquire() as conn:
            chats, _ = await search_attempt_chats(
                conn, redis, attempt_chat_ids=[chat_id], limit=1
            )
    if not chats:
        raise ValueError(f"Attempt chat {chat_id} not found")
    chat = chats[0]

    # Step 1b: Authorization (was MISSING — any authenticated profile could
    # write a grade onto ANY chat). Grading is an instructor mutation, so
    # mirror the attempt read/archive gate (``check_attempt_access``, issue
    # #148): the grader must own the chat's attempt (self-grade) OR hold a
    # strictly-higher instructional role AND share a department with the
    # attempt owner. ``attempt_chat_mv.profile_id`` is the owner's resource
    # profiles_id; compare against ``requester.profiles_id``. ``profile_id`` is
    # MV-derived and may be None pre-hydration on a just-created chat — fail
    # closed in that case (no owner to authorize against). Resolved outside the
    # write transaction so nested pool acquires can't starve a small pool.
    requester = await resolve_profile_identity_context(pool, profile_id, redis)
    owner_profiles_id = chat.profile_id
    if requester is None or owner_profiles_id is None:
        raise HTTPException(
            status_code=403,
            detail="You don't have access to grade this attempt chat.",
        )
    department_in_scope = True
    if owner_profiles_id != requester.profiles_id:
        department_in_scope = await is_profile_in_department_scope(
            pool, requester, owner_profiles_id
        )
    if not check_attempt_access(
        owner_profiles_id,
        requester.profiles_id,
        request_role=requester.role,
        attempt_role=None,
        department_in_scope=department_in_scope,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have access to grade this attempt chat.",
        )

    with timed("db_write"):
     async with pool.acquire() as conn:
        # Step 2: Validate score + derive passed from rubric threshold
        passed = False
        if chat.rubric_id:
            rubrics = await get_rubrics(conn, [chat.rubric_id], redis)
            if rubrics:
                total_points = rubrics[0].total_points or 0
                pass_points = rubrics[0].pass_points or 0
                if total_points > 0 and score > total_points:
                    raise ValueError(
                        f"Score {score} exceeds maximum of {total_points}. "
                        f"Pass threshold is {pass_points}."
                    )
                if score < 0:
                    raise ValueError(
                        f"Score cannot be negative. Valid range: 0–{total_points}."
                    )
                passed = score >= pass_points if pass_points > 0 else score > 0
        else:
            passed = score > 0

        # Step 3: Derive time_taken from chat created_at
        time_taken = 0
        if chat.chat_created_at:
            time_taken = int(
                (datetime.now(timezone.utc) - chat.chat_created_at.replace(tzinfo=timezone.utc)).total_seconds()
            )

        # Step 4: Create grade + link rubric
        result = await create_attempt_grade(
            conn,
            redis, chat_id=chat_id,
            session_id=session_id,
            time_taken=time_taken,
            passed=passed,
            score=score,
            rubric_ids=[chat.rubric_id] if chat.rubric_id else None,
        )

    with timed("refresh"):
        await refresh_attempt_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            targets=["attempt_grade_mv"],
        )

    return {
        "grade_id": str(result.id),
        "chat_id": str(chat_id),
        "score": score,
        "passed": passed,
        "time_taken": time_taken,
    }
