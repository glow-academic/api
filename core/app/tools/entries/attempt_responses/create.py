"""Entry CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.attempt_responses.types import (
    CreateAttemptResponsesResponse,
)


async def create_attempt_responses(
    conn: asyncpg.Connection,
    chat_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    question_ids: list[UUID] | None = None,
    option_ids: list[UUID] | None = None,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateAttemptResponsesResponse:
    """Create an attempt_responses entry."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO attempt_responses_entry
            (id, chat_id, session_id, active, mcp, generated, created_at)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, true, COALESCE($6, NOW()))
        RETURNING id
        """,
        chat_id,
        session_id,
        not soft,
        mcp,
        id,
        created_at,
    )

    if question_ids:
        for question_id in question_ids:
            await conn.execute(
                """
                INSERT INTO attempt_responses_questions_connection
                    (responses_id, question_id)
                VALUES ($1, $2)
                """,
                entry_id,
                question_id,
            )

    if option_ids:
        for option_id in option_ids:
            await conn.execute(
                """
                INSERT INTO attempt_responses_options_connection
                    (responses_id, option_id)
                VALUES ($1, $2)
                """,
                entry_id,
                option_id,
            )

    return CreateAttemptResponsesResponse(id=entry_id)
