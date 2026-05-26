"""Test invocation completion search — filtered/paginated query against test_invocation_completion_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.test_invocation_completion.types import (
    GetTestInvocationCompletionResponse,
)
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "test_invocation_completion_mv"


async def search_test_invocation_completions(
    conn: asyncpg.Connection,
    redis: Redis,
    invocation_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetTestInvocationCompletionResponse]:
    """Search test_invocation_completion entries from test_invocation_completion_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT id, created_at, generated, mcp, active, invocation_id, stop, error, message, call_id
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR invocation_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        invocation_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": str(r["id"]),
            "created_at": r["created_at"],
            "generated": r["generated"],
            "mcp": r["mcp"],
            "active": r["active"],
            "invocation_id": str(r["invocation_id"]) if r["invocation_id"] else None,
            "stop": r["stop"],
            "error": r["error"],
            "message": r["message"],
            "call_id": str(r["call_id"]) if r["call_id"] else None,
        }
        for r in rows
    ]

    invocation_ids_str = (
        {str(i) for i in invocation_ids} if invocation_ids else None
    )

    def matches(row: dict) -> bool:
        if (
            invocation_ids_str is not None
            and str(row.get("invocation_id")) not in invocation_ids_str
        ):
            return False
        return True

    merged = await hedged_search(
        redis,
        "test_invocation_completion",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetTestInvocationCompletionResponse.model_validate(r) for r in merged]
