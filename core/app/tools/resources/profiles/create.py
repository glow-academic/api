"""Profiles CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.profiles.get import get_profiles
from app.tools.resources.profiles.types import GetProfileResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_profile(
    conn: asyncpg.Connection,
    redis: Redis,
    id: UUID | None = None,
    name: str = "",
    description: str = "",
    mcp: bool = False,
    soft: bool = False,
    department_ids: list[UUID] | None = None,
) -> GetProfileResponse:
    """Create a profile resource (plain INSERT, no unique constraint)."""
    profile_id = await conn.fetchval(
        """
        INSERT INTO profiles_resource (id, name, description, active, mcp, generated, department_ids)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, $4, $6)
        RETURNING id
        """,
        name,
        description,
        not soft,
        mcp,
        id,
        department_ids or [],
    )
    await invalidate_tags(["resources", "profiles"], redis=redis)
    items = await get_profiles(conn, [profile_id], redis, bypass_cache=True)
    return items[0]
