"""Entry search — filtered/paginated query against test_invocation_bridge_mv."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.test_invocation_bridge.types import (
    GetTestInvocationBridgeResponse,
)
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "test_invocation_bridge_mv"


async def search_test_invocation_bridge(
    conn: asyncpg.Connection,
    redis: Redis,
    test_invocation_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_cache: bool = False,
) -> list[GetTestInvocationBridgeResponse]:
    """Search test_invocation_bridge from test_invocation_bridge_mv with declarative filters."""
    rows = await conn.fetch(
        f"""
        SELECT test_invocation_id, invocation_id, created_at, active, generated, mcp, session_id
        FROM {MV_NAME}
        WHERE ($1::uuid[] IS NULL OR test_invocation_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        test_invocation_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "bridge_key": f"{r['test_invocation_id']}:{r['invocation_id']}",
            "test_invocation_id": str(r["test_invocation_id"]),
            "invocation_id": str(r["invocation_id"]),
            "created_at": r["created_at"],
            "active": r["active"],
            "generated": r["generated"],
            "mcp": r["mcp"],
            "session_id": str(r["session_id"]),
        }
        for r in rows
    ]

    ti_ids_str = (
        {str(t) for t in test_invocation_ids} if test_invocation_ids else None
    )

    def matches(row: dict) -> bool:
        if ti_ids_str is not None and str(row.get("test_invocation_id")) not in ti_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "test_invocation_bridge",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        id_key="bridge_key",
        bypass_cache=bypass_cache,
    )
    return [GetTestInvocationBridgeResponse.model_validate(r) for r in merged]
