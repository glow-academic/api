"""Attempt highlight search — filtered/paginated query against attempt_highlight_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_highlight.types import (
    GetAttemptHighlightResponse,
)
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "attempt_highlight_mv"


async def search_attempt_highlights(
    conn: asyncpg.Connection,
    redis: Redis,
    strength_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetAttemptHighlightResponse]:
    """Search attempt_highlight entries from attempt_highlight_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT highlight_id, strength_id, section, idx, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR strength_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        strength_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "highlight_id": str(r["highlight_id"]),
            "strength_id": str(r["strength_id"]) if r["strength_id"] else None,
            "section": r["section"],
            "idx": r["idx"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]

    strength_ids_str = {str(s) for s in strength_ids} if strength_ids else None

    def matches(row: dict) -> bool:
        if (
            strength_ids_str is not None
            and str(row.get("strength_id")) not in strength_ids_str
        ):
            return False
        return True

    merged = await hedged_search(
        redis,
        "attempt_highlight",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        id_key="highlight_id",
        bypass_cache=bypass_cache,
    )
    return [GetAttemptHighlightResponse.model_validate(r) for r in merged]
