"""Operations CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.operations.get import get_operations
from app.tools.resources.operations.types import GetOperationResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_operation(
    conn: asyncpg.Connection,
    operation: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetOperationResponse:
    """Create an operation resource (insert or get existing)."""
    operation_id = await conn.fetchval(
        """
        INSERT INTO operations_resource (id, operation, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, $3)
        ON CONFLICT (operation) DO UPDATE SET operation = EXCLUDED.operation
        RETURNING id
    """,
        operation,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "operations"], redis=redis)
    items = await get_operations(conn, [operation_id], redis, bypass_cache=True)
    return items[0]
