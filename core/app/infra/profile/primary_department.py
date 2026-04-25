"""Resolve a department UUID to a primary_departments_resource catalog row.

Callers pass a raw ``departments_id`` (the FK target) and get back the
``primary_departments_resource.id`` to stick into the profile junction.
Lookup-or-create, using the resource's UNIQUE(departments_id) constraint
so repeated calls converge on the same catalog row.
"""

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.resources.primary_departments.create import (
    create_primary_department,
)
from app.tools.resources.primary_departments.search import (
    search_primary_departments,
)


async def resolve_primary_departments_id(
    conn: asyncpg.Connection,
    redis: Redis,
    *,
    departments_id: UUID | None,
    soft: bool = False,
) -> UUID | None:
    """Return the primary_departments_resource.id for a given departments_id."""
    if departments_id is None:
        return None

    existing = await search_primary_departments(
        conn,
        redis,
        limit_count=1,
        departments_ids=[departments_id],
        bypass_cache=True,
    )
    if existing and existing[0].id:
        return existing[0].id

    created = await create_primary_department(
        conn,
        departments_id=departments_id,
        redis=redis,
        soft=soft,
    )
    return created.id
