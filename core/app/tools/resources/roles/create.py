"""Roles CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.roles.get import get_roles
from app.tools.resources.roles.types import GetRoleResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_role(
    conn: asyncpg.Connection,
    redis: Redis,
    id: UUID | None = None,
    name: str = "",
    description: str = "",
    icon_id: UUID | None = None,
    color_id: UUID | None = None,
    level: int = 99,
    permission_ids: list[UUID] | None = None,
    request_limit_ids: list[UUID] | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetRoleResponse:
    """Create a role resource (upsert on UNIQUE (name) constraint)."""
    role_id = await conn.fetchval(
        """
        INSERT INTO roles_resource (id, name, description, icon_id, color_id, level, permission_ids, request_limit_ids, active, mcp, generated)
        VALUES (COALESCE($10, uuidv7()), $1, $2, $3, $4, $5, $6, $7, $8, $9, $9)
        ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
        RETURNING id
        """,
        name,
        description,
        icon_id,
        color_id,
        level,
        permission_ids or [],
        request_limit_ids or [],
        not soft,
        mcp,
        id,
    )
    await invalidate_tags(["resources", "roles"], redis=redis)
    items = await get_roles(conn, [role_id], redis, bypass_cache=True)
    return items[0]
