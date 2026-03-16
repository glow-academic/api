"""attempt_message/get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.attempt_message.types import GetAttemptMessageResponse

MV_NAME = "attempt_message_mv"


async def get_attempt_messages(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetAttemptMessageResponse]:
    """Get attempt_message entries by IDs from attempt_message_mv."""
    if not ids:
        return []

    rows = await conn.fetch(
        f"""
        SELECT message_id, chat_id, attempt_id, type,
               created_at, completed, text_id,
               history_file_path, audio_id
        FROM {MV_NAME}
        WHERE message_id = ANY($1)
        """,
        ids,
    )

    return [GetAttemptMessageResponse(**dict(r)) for r in rows]
