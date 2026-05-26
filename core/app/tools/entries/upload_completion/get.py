"""Uploads Completions GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.upload_completion.types import (
    GetUploadCompletionResponse,
)
from app.utils.cache.hedged_row import read_back_row


async def get_upload_completion(
    conn: asyncpg.Connection,
    completion_id: UUID,
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> GetUploadCompletionResponse | None:
    """Get an upload_completion entry by ID."""
    if not bypass_cache:
        cached = await read_back_row(redis, "upload_completion", completion_id)
        if cached is not None:
            return GetUploadCompletionResponse.model_validate(cached)

    row = await conn.fetchrow(
        """
        SELECT id, upload_id, session_id,
               created_at, active, mcp, generated,
               stop, error, message
        FROM upload_completion_entry
        WHERE id = $1
    """,
        completion_id,
    )

    if row is None:
        return None

    return GetUploadCompletionResponse(
        id=row["id"],
        upload_id=row["upload_id"],
        session_id=row["session_id"],
        created_at=row["created_at"],
        active=row["active"],
        mcp=row["mcp"],
        generated=row["generated"],
        stop=row["stop"],
        error=row["error"],
        message=row["message"],
    )
