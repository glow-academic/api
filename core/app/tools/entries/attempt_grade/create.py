"""Entry CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.attempt_grade.types import CreateAttemptGradeResponse
from app.utils.cache.hedged_row import invalidate_row, write_back_row


async def create_attempt_grade(
    conn: asyncpg.Connection,
    redis: Redis,
    chat_id: UUID,
    session_id: UUID,
    time_taken: int,
    passed: bool,
    score: int,
    id: UUID | None = None,
    rubric_ids: list[UUID] | None = None,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateAttemptGradeResponse:
    """Create an attempt_grade entry."""
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_grade_entry
            (id, chat_id, session_id, time_taken, passed, score, active, mcp, generated, created_at)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true, COALESCE($9, NOW()))
        RETURNING id, created_at
        """,
        chat_id,
        session_id,
        time_taken,
        passed,
        score,
        not soft,
        mcp,
        id,
        created_at,
    )
    if row is None:
        raise ValueError("Failed to create attempt_grade entry")
    entry_id = row["id"]
    actual_created_at = row["created_at"]

    if rubric_ids:
        for rubric_id in rubric_ids:
            await conn.execute(
                """
                INSERT INTO attempt_grade_rubrics_connection
                    (grade_id, rubrics_id, generated)
                VALUES ($1, $2, true)
                """,
                entry_id,
                rubric_id,
            )

    # Write-back cache row matching get/search MV shape. The MV uses
    # DISTINCT ON (chat_id) ORDER BY created_at DESC, so the latest grade
    # for a chat_id wins — and *this* freshly-inserted row IS the latest
    # for chat_id by definition. ``total_points``/``pass_points`` derive
    # from rubric joins; default to None until the MV refreshes. ``rubric_id``
    # picks the first linked rubric_id when present.
    # report-19 HC1: a re-grade inserts a NEW attempt_grade row for the same
    # chat_id. ``attempt_grade_mv`` is DISTINCT ON (chat_id) ORDER BY created_at
    # DESC, so only this latest grade wins on the read side — but the write-back
    # cache keys every grade by its own grade_id, so without invalidation the
    # superseded grade's cache row would survive (both pass ``hedged_search``'s
    # chat_id filter, dedup is by grade_id) and ``search_attempt_grades`` would
    # return TWO grades for one chat for up to _TTL. Wire the supersede flow the
    # prior FLAG prescribed: bust every prior grade's cache row for this chat
    # before caching the fresh (latest) one, so the hedged read honours the same
    # DISTINCT-ON-(chat_id) contract as the MV.
    fresh_row = {
        "grade_id": str(entry_id),
        "chat_id": str(chat_id),
        "score": float(score),
        "passed": passed,
        "time_taken": time_taken,
        "total_points": None,
        "pass_points": None,
        "rubric_id": str(rubric_ids[0]) if rubric_ids else None,
        "created_at": actual_created_at.isoformat() if actual_created_at else None,
        "id": str(entry_id),
    }
    if actual_created_at is not None:
        # Supersede prior cached grades for this chat (HC1) — invalidate_row
        # deletes the per-id cache key, which drops it from hedged_search
        # (the recent-ZSET ref MGET-misses and ages out under the cap).
        prior_grades = await conn.fetch(
            "SELECT id FROM attempt_grade_entry WHERE chat_id = $1 AND id <> $2",
            chat_id,
            entry_id,
        )
        for prior in prior_grades:
            await invalidate_row(redis, "attempt_grade", prior["id"])

        await write_back_row(
            redis,
            "attempt_grade",
            entry_id,
            fresh_row,
            score_ms=int(actual_created_at.timestamp() * 1000),
        )

    return CreateAttemptGradeResponse(id=entry_id)
