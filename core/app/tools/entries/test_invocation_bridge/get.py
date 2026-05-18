"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.entries.test_invocation_bridge.types import (
    GetTestInvocationBridgeResponse,
)

MV_NAME = "test_invocation_bridge_mv"


async def get_test_invocation_bridge(
    conn: asyncpg.Connection,
    test_invocation_ids: list[UUID],
) -> list[GetTestInvocationBridgeResponse]:
    """Get test_invocation_bridge entries by test_invocation_id from MV."""
    if not test_invocation_ids:
        return []
    rows = await conn.fetch(
        f"SELECT * FROM {MV_NAME} WHERE test_invocation_id = ANY($1)",
        test_invocation_ids,
    )
    return [GetTestInvocationBridgeResponse(**dict(r)) for r in rows]
