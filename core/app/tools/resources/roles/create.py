"""Roles CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.roles.get import get_roles
from app.tools.resources.roles.types import GetRoleResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_role(
    conn: asyncpg.Connection,
    role: str,
    redis: Redis,
    id: UUID | None = None,
    name: str = "",
    description: str = "",
    icon_id: UUID | None = None,
    color_id: UUID | None = None,
    artifacts: list[str] | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetRoleResponse:
    """Create a role resource (upsert on UNIQUE (role, name) constraint)."""
    role_id = await conn.fetchval(
        """
        INSERT INTO roles_resource (id, role, name, description, icon_id, color_id, artifacts, active, mcp, generated)
        VALUES (COALESCE($9, uuidv7()), $1, $2, $3, $4, $5, $6, $7, $8, $8)
        ON CONFLICT (role, name) DO UPDATE SET role = EXCLUDED.role
        RETURNING id
        """,
        role,
        name,
        description,
        icon_id,
        color_id,
        artifacts or [],
        not soft,
        mcp,
        id,
    )
    await invalidate_tags(["resources", "roles"], redis=redis)
    items = await get_roles(conn, [role_id], redis, bypass_cache=True)
    return items[0]
