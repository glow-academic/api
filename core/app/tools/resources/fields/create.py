"""Fields CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.fields.get import get_fields
from app.tools.resources.fields.types import GetFieldResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_field(
    conn: asyncpg.Connection,
    name: str = "",
    description: str = "",
    redis: Redis = None,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    department_ids: list[UUID] | None = None,
    conditional_parameter_ids: list[UUID] | None = None,
) -> GetFieldResponse:
    """Create a field resource (plain INSERT — no unique constraint)."""
    field_id = await conn.fetchval(
        """
        INSERT INTO fields_resource (id, name, description, value, active, mcp, generated,
            department_ids, conditional_parameter_ids)
        VALUES (COALESCE($5, uuidv7()), $1, $2, '', $3, $4, $4,
            $6, $7)
        RETURNING id
        """,
        name,
        description,
        not soft,
        mcp,
        id,
        department_ids or [],
        conditional_parameter_ids or [],
    )
    await invalidate_tags(["resources", "fields"], redis=redis)
    items = await get_fields(conn, [field_id], redis, bypass_cache=True)
    return items[0]
