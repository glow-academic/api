"""Attempt message CREATE — reusable data-access layer."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.attempt_message.types import (
    CreateAttemptMessageResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_attempt_message(
    conn: asyncpg.Connection,
    redis: Redis,
    chat_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    created_at: datetime | None = None,
) -> CreateAttemptMessageResponse:
    """Create an attempt_message_entry row. Text-only — audio attaches
    are separate entries created via ``create_attempt_audio``.
    """
    row = await conn.fetchrow(
        """
        INSERT INTO attempt_message_entry (id, chat_id, session_id, active, mcp, generated, created_at)
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

    if row is None:
        raise ValueError("Failed to create attempt_message entry")

    entry_id = row["id"]
    actual_created_at = row["created_at"]

    # Write-back cache row matching get/search MV shape. ``text_id``/``audios_id``
    # link in via child upload primitives (text_uploads/audio_uploads); ``attempt_id``
    # is derived via the MV's chat→attempt join. ``parent_message_id`` lives in
    # ``attempt_message_tree_entry`` and is set by the caller after this insert.
    # ``sibling_index``/``sibling_count`` default to 0/1: a freshly inserted
    # message is a single sibling until a tree-fork adds siblings.
    fresh_row = {
        "message_id": str(entry_id),
        "chat_id": str(chat_id),
        "attempt_id": None,
        "type": None,
        "created_at": actual_created_at.isoformat() if actual_created_at else None,
        "completed": False,
        "text_id": None,
        "history_file_path": None,
        "audios_id": None,
        "parent_message_id": None,
        "sibling_index": 0,
        "sibling_count": 1,
        # Synthetic id alias for hedged_search dedup (default id_key="id").
        "id": str(entry_id),
    }
    if actual_created_at is not None:
        await write_back_row(
            redis,
            "attempt_message",
            entry_id,
            fresh_row,
            score_ms=int(actual_created_at.timestamp() * 1000),
        )

    return CreateAttemptMessageResponse(id=entry_id)
