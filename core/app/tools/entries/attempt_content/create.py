"""Entry CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.attempt_content.types import (
    CreateAttemptContentResponse,
)


async def create_attempt_content(
    conn: asyncpg.Connection,
    redis: Redis,
    message_id: UUID,
    session_id: UUID,
    content: str,
    persona_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateAttemptContentResponse:
    """Create an attempt_content entry."""
    entry_id = await conn.fetchval(
        """
        INSERT INTO attempt_content_entry
            (id, message_id, session_id, content, persona_id, active, mcp, generated, created_at)
        VALUES (COALESCE($7, uuidv7()), $1, $2, $3, $4, $5, $6, true, COALESCE($8, NOW()))
        RETURNING id
        """,
        message_id,
        session_id,
        content,
        persona_id,
        not soft,
        mcp,
        id,
        created_at,
    )

    return CreateAttemptContentResponse(id=entry_id)
