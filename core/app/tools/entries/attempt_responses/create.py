"""Entry CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.attempt_responses.types import (
    CreateAttemptResponsesResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_attempt_responses(
    conn: asyncpg.Connection,
    redis: Redis,
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
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_responses_entry
            (id, chat_id, session_id, active, mcp, generated, created_at)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, true, COALESCE($6, NOW()))
        RETURNING id, created_at
        """,
        chat_id,
        session_id,
        not soft,
        mcp,
        id,
        created_at,
    )
    entry_id = row["id"]
    actual_created_at = row["created_at"]

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

    # Cache row mirrors MV shape (DISTINCT ON response_id; one row per response).
    # MV picks a single question/option via the join; use the first of each here.
    first_question_id = str(question_ids[0]) if question_ids else None
    first_option_id = str(option_ids[0]) if option_ids else None
    fresh_row = {
        "response_id": str(entry_id),
        "chat_id": str(chat_id),
        "question_id": first_question_id,
        "option_id": first_option_id,
        "created_at": actual_created_at.isoformat(),
    }
    await write_back_row(
        redis,
        "attempt_responses",
        entry_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )

    return CreateAttemptResponsesResponse(id=entry_id)
