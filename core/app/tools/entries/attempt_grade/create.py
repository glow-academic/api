"""Entry CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.attempt_grade.types import CreateAttemptGradeResponse


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
    entry_id = await conn.fetchval(
        """
        INSERT INTO attempt_grade_entry
            (id, chat_id, session_id, time_taken, passed, score, active, mcp, generated, created_at)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true, COALESCE($9, NOW()))
        RETURNING id
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

    return CreateAttemptGradeResponse(id=entry_id)
