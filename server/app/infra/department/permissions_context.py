"""Department permissions context + shared save helpers.

Permissions context:
  1. resolve_department_permissions_context — lightweight access + edit check

Shared save helpers (used by both create and update):
  2. resolve_department_values — raw string → resource ID resolution
  3. create_denormalized_snapshot — hydrate IDs → departments_resource snapshot

Department is special: it IS a department, so there are no parent department_ids
for access control. Access is role-based only (member+).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.department.get import (
    get_departments as get_department_artifacts,
)
from app.tools.resources.departments.create import (
    create_department as create_department_resource,
)
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names

if TYPE_CHECKING:
    from app.infra.department.create import (
        CreateDepartmentItem,
        DepartmentFieldError,
    )
    from app.infra.department.types import (
        UpdateDepartmentItem,
    )


@dataclass(frozen=True)
class DepartmentPermissionsContext:
    """Lightweight context for department permission checks."""

    exists: bool
    usage_count: int


async def resolve_department_permissions_context(
    conn: asyncpg.Connection,
    department_id: UUID,
) -> DepartmentPermissionsContext:
    """Fetch just what's needed for department permission checks.

    Steps:
      1. get_department_artifacts → exists check
      2. Count usage across profile/simulation/scenario/persona/document/cohort junctions
    """
    artifacts = await get_department_artifacts(conn, [department_id])

    if not artifacts:
        return DepartmentPermissionsContext(
            exists=False,
            usage_count=0,
        )

    # Count how many artifacts reference this department across all junction tables
    usage_count = await conn.fetchval(
        """
        SELECT (
            (SELECT COUNT(*) FROM profile_departments_junction WHERE departments_id = $1 AND active = true) +
            (SELECT COUNT(*) FROM simulation_departments_junction WHERE departments_id = $1 AND active = true) +
            (SELECT COUNT(*) FROM scenario_departments_junction WHERE departments_id = $1 AND active = true) +
            (SELECT COUNT(*) FROM persona_departments_junction WHERE departments_id = $1 AND active = true) +
            (SELECT COUNT(*) FROM document_departments_junction WHERE departments_id = $1 AND active = true) +
            (SELECT COUNT(*) FROM cohort_departments_junction WHERE departments_id = $1 AND active = true)
        )::bigint
        """,
        department_id,
    )

    return DepartmentPermissionsContext(
        exists=True,
        usage_count=usage_count or 0,
    )


# ---------------------------------------------------------------------------
# Shared save helpers — used by both department_create and department_update
# ---------------------------------------------------------------------------


async def resolve_department_values(
    conn: asyncpg.Connection,
    redis: Redis,
    item: CreateDepartmentItem | UpdateDepartmentItem,
    is_create: bool,
) -> list[DepartmentFieldError]:
    """Resolve raw value fields to resource IDs (mutates item in place).

    For 'create' resources (name, description):
      Creates a new resource via the create tool.

    Returns a list of errors (empty if all resolved).
    """
    from app.infra.department.create import DepartmentFieldError

    errors: list[DepartmentFieldError] = []

    # --- Create resources ---

    if item.name is not None and item.name_id is None:
        result = await create_name(conn, item.name, redis)
        item.name_id = result.id

    if item.description is not None and item.description_id is None:
        result = await create_description(conn, item.description, redis)
        item.description_id = result.id

    # --- Match resources ---

    if item.active_flag is not None and item.active_flag_id is None:
        results = await search_flags(
            conn,
            redis,
            search=None,
            flag_type="department_active",
            limit_count=100,
        )
        match = next((r for r in results if r.type == "department_active"), None)
        if match and match.id:
            if item.active_flag:
                item.active_flag_id = match.id
        elif item.active_flag:
            errors.append(
                DepartmentFieldError(
                    field="active_flag", message="Active flag resource not found"
                )
            )

    # --- Validate required fields (create only) ---

    if is_create:
        if item.name_id is None:
            errors.append(
                DepartmentFieldError(field="name", message="Name is required")
            )

    return errors


async def create_denormalized_snapshot(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    id: UUID | None = None,
    name_id: UUID | None,
    description_id: UUID | None,
    setting_ids: list[UUID] | None = None,
) -> UUID:
    """Create a departments_resource snapshot by hydrating IDs to values.

    Each parallel branch acquires its own connection from the pool.
    """

    async def _get_names() -> list:
        if not name_id:
            return []
        async with pool.acquire() as conn:
            return await get_names(conn, [name_id], redis, bypass_cache=True)

    async def _get_descriptions() -> list:
        if not description_id:
            return []
        async with pool.acquire() as conn:
            return await get_descriptions(
                conn, [description_id], redis, bypass_cache=True
            )

    names, descriptions = await asyncio.gather(
        _get_names(),
        _get_descriptions(),
    )

    async with pool.acquire() as conn:
        result = await create_department_resource(
            conn,
            id=id,
            name=names[0].name if names else "",
            description=descriptions[0].description if descriptions else "",
            redis=redis,
            setting_ids=setting_ids,
        )
    return result.id
