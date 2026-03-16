"""Provider Keys CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.provider_keys.get import get_provider_keys
from app.tools.resources.provider_keys.types import GetProviderKeyResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_provider_key(
    conn: asyncpg.Connection,
    provider_id: UUID,
    key_id: UUID,
    redis: Redis,
    id: UUID | None = None,
    key: str = "",
    name: str = "",
    description: str = "",
    mcp: bool = False,
    soft: bool = False,
) -> GetProviderKeyResponse:
    """Create a provider_key resource (plain INSERT — no unique constraint)."""
    provider_key_id = await conn.fetchval(
        """
        INSERT INTO provider_keys_resource (id, provider_id, key_id, key, name, description, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, $7)
        RETURNING id
        """,
        provider_id,
        key_id,
        key,
        name,
        description,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "provider_keys"], redis=redis)
    items = await get_provider_keys(conn, [provider_key_id], redis, bypass_cache=True)
    return items[0]
