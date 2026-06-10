"""Icons CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.icons.get import get_icons
from app.tools.resources.icons.types import GetIconResponse
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.svg_safety import sanitize_icon_value


async def create_icon(
    conn: asyncpg.Connection,
    name: str,
    description: str,
    value: str,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetIconResponse:
    """Create an icon resource.

    The ``value`` is sanitized on write (see ``sanitize_icon_value``):
    raw inline SVG is rebuilt from a safe allowlist and named identifiers
    pass through, so a malicious SVG payload can never be persisted. This
    is the single write boundary for icon values, complementing the
    client-side render sanitization (DOMPurify).
    """
    value = sanitize_icon_value(value)
    icon_id = await conn.fetchval(
        """
        INSERT INTO icons_resource (id, name, description, value, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, $5)
        RETURNING id
    """,
        name,
        description,
        value,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "icons"], redis=redis)
    items = await get_icons(conn, [icon_id], redis, bypass_cache=True)
    return items[0]
