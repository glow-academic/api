"""Entry search — filtered/paginated query against test_invocation_bridge_mv."""

from uuid import UUID

import asyncpg

from app.tools.entries.test_invocation_bridge.types import (
    GetTestInvocationBridgeResponse,
)

MV_NAME = "test_invocation_bridge_mv"


async def search_test_invocation_bridge(
    conn: asyncpg.Connection,
    test_invocation_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[GetTestInvocationBridgeResponse]:
    """Search test_invocation_bridge from test_invocation_bridge_mv with declarative filters."""
    rows = await conn.fetch(
        f"""
        SELECT *
        FROM {MV_NAME}
        WHERE ($1::uuid[] IS NULL OR test_invocation_id = ANY($1))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        test_invocation_ids,
        limit,
        offset,
    )
    return [GetTestInvocationBridgeResponse(**dict(r)) for r in rows]
