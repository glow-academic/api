"""Providers CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.providers.get import get_providers
from app.tools.resources.providers.types import GetProviderResponse
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.url_safety import validate_endpoint_url


async def create_provider(
    conn: asyncpg.Connection,
    name: str = "",
    description: str = "",
    redis: Redis = None,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    department_ids: list[UUID] | None = None,
    endpoint: str | None = None,
    key: str | None = None,
    value: str | None = None,
) -> GetProviderResponse:
    """Create a provider resource (plain INSERT — no unique constraint).

    The denormalized ``endpoint`` is read back as the outbound litellm
    ``base_url`` (see ``prepare_pipeline``), so SSRF-validate any
    non-empty value before persisting (raises ``ValueError`` → HTTP 400).
    """
    if endpoint:
        validate_endpoint_url(endpoint)

    provider_id = await conn.fetchval(
        """
        INSERT INTO providers_resource (id, name, description, active, mcp, generated, department_ids, endpoint, key, value)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, $4, $4, $6, $7, $8, $9)
        RETURNING id
        """,
        name,
        description,
        not soft,
        mcp,
        id,
        department_ids or [],
        endpoint or "",
        key or "",
        value or "",
    )
    await invalidate_tags(["resources", "providers"], redis=redis)
    items = await get_providers(conn, [provider_id], redis, bypass_cache=True)
    return items[0]
