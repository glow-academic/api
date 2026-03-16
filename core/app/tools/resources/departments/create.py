"""Departments CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.departments.get import get_departments
from app.tools.resources.departments.types import GetDepartmentResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_department(
    conn: asyncpg.Connection,
    name: str = "",
    description: str = "",
    redis: Redis = None,
    setting_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    is_primary: bool = False,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetDepartmentResponse:
    """Create a department resource (plain INSERT — no unique constraint)."""
    dept_id = await conn.fetchval(
        """
        INSERT INTO departments_resource (
            id, name, description, setting_ids, department_ids, is_primary, active, mcp, generated
        )
        VALUES (COALESCE($8, uuidv7()), $1, $2, $3, $4, $5, $6, $7, $7)
        RETURNING id
        """,
        name,
        description,
        setting_ids or [],
        department_ids or [],
        is_primary,
        not soft,
        mcp,
        id,
    )
    await invalidate_tags(["resources", "departments"], redis=redis)
    items = await get_departments(conn, [dept_id], redis, bypass_cache=True)
    return items[0]
