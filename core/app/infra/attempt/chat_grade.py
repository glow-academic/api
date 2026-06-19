"""Attempt chat grade — thin infra impl for generate pipeline.

Model passes: chat_id, score.
Infra derives: passed (from rubric threshold), time_taken (from timestamps).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.attempt.permissions import enforce_attempt_access_by_chat
from app.infra.attempt.refresh import refresh_attempt_impl
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
    # mirror the attempt read/archive gate (issue #148): the grader must own the
    # chat's attempt (self-grade) OR hold a strictly-higher instructional role
    # AND share a department with the attempt owner. Routed through the shared
    # attempt-mutation path so this whole class is gated identically and can't
    # regress per-endpoint. The chat owner (``attempt_chat_mv.profile_id``) may
    # be None pre-hydration on a just-created chat — the helper fails closed.
    # Resolved outside the write transaction so nested pool acquires can't
    # starve a small pool.
    requester = await resolve_profile_identity_context(pool, profile_id, redis)
    await enforce_attempt_access_by_chat(
        pool, redis, chat_id=chat_id, requester=requester,
        deny_detail="You don't have access to grade this attempt chat.",
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
                # A rubric bounds the score to its max — INCLUDING a 0-total
                # rubric, against which any positive score is invalid (F4: the
                # old ``total_points > 0`` guard skipped the check at 0, letting
                # a score > 0 be stored against a 0-max rubric).
                if score > total_points:
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
