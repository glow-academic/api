"""Upload completion search — filtered/paginated query against upload_completion_mv."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.upload_completion.types import (
    SearchUploadCompletionResponse,
)

MV_NAME = "upload_completion_mv"


async def search_upload_completions(
    conn: asyncpg.Connection,
    upload_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
) -> list[SearchUploadCompletionResponse]:
    """Search upload_completions from upload_completion_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, created_at, generated, mcp, active, upload_id, session_id, stop, error, message
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR upload_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        upload_ids,
        limit,
        offset,
    )

    return [SearchUploadCompletionResponse(**dict(r)) for r in rows]
