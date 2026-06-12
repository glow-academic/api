"""Entry CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.image_completion.types import (
    CreateImageCompletionResponse,
)
from app.utils.cache.hedged_row import write_back_row


async def create_image_completion(
    conn: asyncpg.Connection,
    redis: Redis,
    image_id: UUID,
    session_id: UUID,
    id: UUID | None = None,
    stop: bool = False,
    error: bool = False,
    message: str = "",
    mcp: bool = False,
    soft: bool = False,
) -> CreateImageCompletionResponse:
    """Create a image_completion entry.

    ``UNIQUE(image_id)`` means at most one completion row per image. A hard
    completion supersedes a DORMANT soft proposal via ``ON CONFLICT DO UPDATE``;
    an accepted completion is never clobbered and a duplicate hard completion is
    idempotent (no 2nd active row) — mirroring the attempt_completion #339 B1
    fix (C1-B).
    """
    incoming_active = not soft
    row = await conn.fetchrow(
        """
        INSERT INTO image_completion_entry (id, image_id, session_id, stop, error, message, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, true)
        ON CONFLICT (image_id) DO UPDATE
            SET active = true,
                session_id = EXCLUDED.session_id,
                stop = EXCLUDED.stop,
                error = EXCLUDED.error,
                message = EXCLUDED.message,
                mcp = EXCLUDED.mcp
            WHERE image_completion_entry.active = false
              AND EXCLUDED.active = true
        RETURNING id, created_at, active, stop, error, message, mcp, session_id
        """,
        image_id,
        session_id,
        stop,
        error,
        message,
        incoming_active,
        mcp,
        id,
    )
    if row is None:
        existing = await conn.fetchrow(
            "SELECT id, active FROM image_completion_entry WHERE image_id = $1",
            image_id,
        )
        return CreateImageCompletionResponse(
            id=existing["id"], active=existing["active"]
        )

    entry_id = row["id"]
    actual_created_at = row["created_at"]

    fresh_row = {
        "id": str(entry_id),
        "image_id": str(image_id),
        "session_id": str(row["session_id"]),
        "created_at": actual_created_at.isoformat(),
        "active": row["active"],
        "mcp": row["mcp"],
        "generated": True,
        "stop": row["stop"],
        "error": row["error"],
        "message": row["message"],
    }
    await write_back_row(
        redis,
        "image_completion",
        entry_id,
        fresh_row,
        score_ms=int(actual_created_at.timestamp() * 1000),
    )

    return CreateImageCompletionResponse(id=entry_id, active=row["active"])
