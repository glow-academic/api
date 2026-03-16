"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.attempt_grade.types import CreateAttemptGradeResponse


async def create_attempt_grade(
    conn: asyncpg.Connection,
    chat_id: UUID,
    call_id: UUID,
    run_id: UUID,
    time_taken: int,
    passed: bool,
    score: int,
    id: UUID | None = None,
    rubric_ids: list[UUID] | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> CreateAttemptGradeResponse:
    """Create an attempt_grade entry."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO attempt_grade_entry
            (id, chat_id, call_id, run_id, time_taken, passed, score, active, mcp, generated)
        VALUES (COALESCE($9, uuidv7()), $1, $2, $3, $4, $5, $6, $7, $8, true)
        RETURNING id
        """,
        chat_id,
        call_id,
        run_id,
        time_taken,
        passed,
        score,
        not soft,
        mcp,
        id,
    )

    if rubric_ids:
        for rubric_id in rubric_ids:
            await conn.execute(
                """
                INSERT INTO attempt_chat_rubrics_connection
                    (attempt_chat_id, rubrics_id, generated)
                VALUES ($1, $2, true)
                """,
                chat_id,
                rubric_id,
            )

    return CreateAttemptGradeResponse(id=entry_id)
