"""Permissions CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.permissions.get import get_permissions
from app.tools.resources.permissions.types import GetPermissionResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_permission(
    conn: asyncpg.Connection,
    artifact: str,
    operation: str,
    redis: Redis,
    name: str = "",
    description: str = "",
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetPermissionResponse:
    """Create a permission resource (insert or get existing)."""
    permission_id = await conn.fetchval(
        """
        INSERT INTO permissions_resource (id, artifact, operation, name, description, active, mcp, generated)
        VALUES (COALESCE($7, uuidv7()), $1::artifact_type, $2::operation_type, $3, $4, $5, $6, $6)
        ON CONFLICT (artifact, operation) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description
        RETURNING id
        """,
        artifact,
        operation,
        name,
        description,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "permissions"], redis=redis)
    items = await get_permissions(conn, [permission_id], redis, bypass_cache=True)
    return items[0]
