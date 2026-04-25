"""Primary Departments CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.primary_departments.get import (
    get_primary_departments,
)
from app.tools.resources.primary_departments.types import (
    GetPrimaryDepartmentResponse,
)
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_primary_department(
    conn: asyncpg.Connection,
    departments_id: UUID,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetPrimaryDepartmentResponse:
    """Create a primary_departments_resource row.

    At most one row per departments_id (UNIQUE constraint); repeated calls
    reactivate or no-op the existing row.
    """
    row_id = await conn.fetchval(
        """
        INSERT INTO primary_departments_resource (id, departments_id, active, mcp, generated)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3, $3)
        ON CONFLICT (departments_id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id
        """,
        departments_id,
        not soft,
        mcp,
        id,
    )

    await invalidate_tags(["resources", "primary_departments"], redis=redis)
    items = await get_primary_departments(conn, [row_id], redis, bypass_cache=True)
    return items[0]
