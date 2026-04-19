"""Logins CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.logins.get import get_logins
from app.tools.resources.logins.types import GetLoginsResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_logins(
    conn: asyncpg.Connection,
    profile_id: UUID | None = None,
    auth_id: UUID | None = None,
    icon_id: UUID | None = None,
    display_name: str = "",
    login_type: str = "auth",
    id: UUID | None = None,
    mcp: bool = False,
    redis: Redis = None,
    soft: bool = False,
) -> GetLoginsResponse:
    """Create a logins resource (plain INSERT — no unique constraint)."""
    logins_id = await conn.fetchval(
        """
        INSERT INTO logins_resource (id, profile_id, auth_id, icon_id, display_name, login_type, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, $7)
        RETURNING id
        """,
        profile_id,
        auth_id,
        icon_id,
        display_name,
        login_type,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "logins"], redis=redis)
    items = await get_logins(conn, [logins_id], redis, bypass_cache=True)
    return items[0]
