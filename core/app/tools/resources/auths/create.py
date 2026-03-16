"""Auths CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.auths.get import get_auths
from app.tools.resources.auths.types import GetAuthResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_auth(
    conn: asyncpg.Connection,
    redis: Redis,
    id: UUID | None = None,
    name: str = "",
    description: str = "",
    mcp: bool = False,
    soft: bool = False,
    department_ids: list[UUID] | None = None,
    slug: str | None = None,
    protocol: str | None = None,
) -> GetAuthResponse:
    """Create an auth resource (plain INSERT — no unique constraint)."""
    auth_id = await conn.fetchval(
        """
        INSERT INTO auths_resource (id, name, description, department_ids, slug, protocol, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, $7)
        RETURNING id
        """,
        name,
        description,
        department_ids or [],
        slug,
        protocol,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "auths"], redis=redis)
    items = await get_auths(conn, [auth_id], redis, bypass_cache=True)
    return items[0]
