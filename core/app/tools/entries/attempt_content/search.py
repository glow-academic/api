"""Attempt content search — filtered/paginated query against attempt_content_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_content.types import GetAttemptContentResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "attempt_content_mv"


async def search_attempt_contents(
    conn: asyncpg.Connection,
    redis: Redis,
    message_ids: list[UUID] | None = None,
    persona_entry_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetAttemptContentResponse]:
    """Search attempt contents from attempt_content_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT content_id, message_id, content, persona_entry_id, idx, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR message_id = ANY($1))
          AND ($2::uuid[] IS NULL OR persona_entry_id = ANY($2))
        ORDER BY created_at DESC
        LIMIT $3 OFFSET $4
        """,
        message_ids,
        persona_entry_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "content_id": str(r["content_id"]),
            "message_id": str(r["message_id"]) if r["message_id"] else None,
            "content": r["content"],
            "persona_entry_id": (
                str(r["persona_entry_id"]) if r["persona_entry_id"] else None
            ),
            "idx": r["idx"],
            "created_at": r["created_at"],
            "id": str(r["content_id"]),
        }
        for r in rows
    ]

    message_ids_str = {str(m) for m in message_ids} if message_ids else None
    persona_ids_str = (
        {str(p) for p in persona_entry_ids} if persona_entry_ids else None
    )

    def matches(row: dict) -> bool:
        if message_ids_str is not None and str(row.get("message_id")) not in message_ids_str:
            return False
        if (
            persona_ids_str is not None
            and str(row.get("persona_entry_id")) not in persona_ids_str
        ):
            return False
        return True

    merged = await hedged_search(
        redis,
        "attempt_content",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        id_key="content_id",
        bypass_cache=bypass_cache,
    )
    return [GetAttemptContentResponse.model_validate(r) for r in merged]
