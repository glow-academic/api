"""Settings CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.settings.get import get_settings
from app.tools.resources.settings.types import GetSettingResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_setting(
    conn: asyncpg.Connection,
    name: str = "",
    description: str = "",
    redis: Redis = None,
    department_ids: list[UUID] | None = None,
    provider_key_ids: list[UUID] | None = None,
    auth_ids: list[UUID] | None = None,
    system_ids: list[UUID] | None = None,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetSettingResponse:
    """Create a setting resource (plain INSERT — no unique constraint)."""
    setting_id = await conn.fetchval(
        """
        INSERT INTO settings_resource (
            id, name, description, department_ids, provider_key_ids, auth_ids, system_ids, active, mcp, generated
        )
        VALUES (COALESCE($9, uuidv7()), $1, $2, $3, $4, $5, $6, $7, $8, $8)
        RETURNING id
        """,
        name,
        description,
        department_ids or [],
        provider_key_ids or [],
        auth_ids or [],
        system_ids or [],
        not soft,
        mcp,
        id,
    )
    await invalidate_tags(["resources", "settings"], redis=redis)
    items = await get_settings(conn, [setting_id], redis, bypass_cache=True)
    return items[0]
