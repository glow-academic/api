"""Attempt archive search — filtered/paginated query against attempt_archive_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_archive.types import GetAttemptArchiveResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "attempt_archive_mv"


async def search_attempt_archives(
    conn: asyncpg.Connection,
    redis: Redis,
    attempt_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetAttemptArchiveResponse]:
    """Search attempt_archive entries from attempt_archive_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, created_at, generated, mcp, active, attempt_id, archived, session_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR attempt_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        attempt_ids,
        limit + offset + 1000,
        0,
    )
    mv_dicts = [dict(r) for r in rows]

    attempt_ids_str = {str(a) for a in attempt_ids} if attempt_ids else None

    def matches(row: dict) -> bool:
        if attempt_ids_str is not None and str(row.get("attempt_id")) not in attempt_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "attempt_archive",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetAttemptArchiveResponse.model_validate(r) for r in merged]
