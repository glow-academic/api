"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.test_invocation_bridge.types import (
    GetTestInvocationBridgeResponse,
)
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "test_invocation_bridge_mv"


async def get_test_invocation_bridge(
    conn: asyncpg.Connection,
    test_invocation_ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetTestInvocationBridgeResponse]:
    """Get test_invocation_bridge entries by test_invocation_id (with cache hedge).

    Composite-PK bridge keyed by ``(test_invocation_id, invocation_id)`` —
    cached as synthetic ``bridge_key``; merged with MV result.
    """
    if not test_invocation_ids:
        return []
    rows = await conn.fetch(
        f"SELECT * FROM {MV_NAME} WHERE test_invocation_id = ANY($1)",
        test_invocation_ids,
    )
    mv_dicts = [
        {
            "bridge_key": f"{r['test_invocation_id']}:{r['invocation_id']}",
            "test_invocation_id": (
                str(r["test_invocation_id"]) if r["test_invocation_id"] else None
            ),
            "invocation_id": (
                str(r["invocation_id"]) if r["invocation_id"] else None
            ),
            "session_id": str(r["session_id"]) if r.get("session_id") else None,
            "created_at": r["created_at"],
            "active": r.get("active", True),
            "generated": r.get("generated", True),
            "mcp": r.get("mcp", False),
        }
        for r in rows
    ]
    ti_ids_str = {str(t) for t in test_invocation_ids}

    def matches(row: dict) -> bool:
        return str(row.get("test_invocation_id")) in ti_ids_str

    merged = await hedged_search(
        redis,
        "test_invocation_bridge",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=10000,
        offset=0,
        id_key="bridge_key",
        bypass_cache=bypass_cache,
    )
    return [GetTestInvocationBridgeResponse.model_validate(r) for r in merged]
