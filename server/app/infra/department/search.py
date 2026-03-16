"""Department search logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments, name)
  2. search_departments (artifact) — core artifact search (IDs + total_count)
  3. get_departments (artifact) — hydrate junction IDs
  4. Resource get tools — hydrate names, descriptions
  5. resolve_department_permissions_context — usage counts for permissions
  6. search_profiles (artifact) — staff counts per department
  7. Permissions — compute per-department can_edit, can_delete, can_duplicate
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.department.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.department.permissions_context import (
    DepartmentPermissionsContext,
    resolve_department_permissions_context,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.department.types import (
    ListDepartmentApiDepartment,
    ListDepartmentApiResponse,
)
from app.tools.artifacts.department.get import get_departments
from app.tools.artifacts.department.search import (
    search_departments as search_department_artifacts,
)
from app.tools.artifacts.profile.search import (
    search_profiles as search_profile_artifacts,
)
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.names.get import get_names

DEPARTMENT_IMPORT_FIELDS: list[dict[str, Any]] = [
    {
        "key": "name",
        "label": "Name",
        "required": True,
        "example": "Nursing",
        "description": "The department's display name",
    },
    {
        "key": "description",
        "label": "Description",
        "example": "Nursing department for clinical training...",
        "description": "Optional description",
    },
    {
        "key": "active_flag",
        "label": "Active",
        "type": "boolean",
        "example": "true",
        "description": "Whether the department is active (true/false)",
    },
]


async def search_department_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Main filters
    search: str | None = None,
    # Pagination
    page_size: int = 12,
    page_offset: int = 0,
) -> ListDepartmentApiResponse:
    """Department search using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, departments, name
      2. search_departments → (department_artifact_ids, total_count)
      3. get_departments → hydrate junction IDs
      4. Parallel: hydrate resources + permissions contexts + staff counts
      5. Build department list with permissions
    """
    from fastapi import HTTPException

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    user_role = profile.role
    actor_name = profile.name

    # ── Step 2: Search departments ─────────────────────────────────────

    async with pool.acquire() as conn:
        department_ids, total_count = await search_department_artifacts(
            conn,
            search=search,
            limit_count=page_size,
            offset_count=page_offset,
        )

    if not department_ids:
        return _empty_response(actor_name, total_count=0)

    # ── Step 3: Get department artifacts with junction IDs ─────────────

    async with pool.acquire() as conn:
        artifacts = await get_departments(
            conn,
            department_ids,
            names=True,
            descriptions=True,
            flags=True,
            departments=True,
        )

    # ── Step 4: Parallel hydration + permissions + staff counts ────────

    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])

    # Build parallel tasks

    async def _fetch_names() -> list:
        if not all_name_ids:
            return []
        async with pool.acquire() as conn:
            return await get_names(conn, all_name_ids, redis)

    async def _fetch_descriptions() -> list:
        if not all_description_ids:
            return []
        async with pool.acquire() as conn:
            return await get_descriptions(conn, all_description_ids, redis)

    # Per-department: resolve permissions context + staff count
    # permissions_context gives us usage_count
    # search_profiles with department_ids gives us staff_count via total_count

    async def _fetch_perm(artifact_id: UUID) -> DepartmentPermissionsContext:
        async with pool.acquire() as conn:
            return await resolve_department_permissions_context(conn, artifact_id)

    async def _fetch_staff(dept_ids: list[UUID] | None) -> int:
        async with pool.acquire() as conn:
            return await _staff_count_for_department(conn, dept_ids)

    perm_tasks = [_fetch_perm(a.id) for a in artifacts]
    staff_tasks = [_fetch_staff(a.department_ids) for a in artifacts]

    # Gather all
    results = await asyncio.gather(
        _fetch_names(),
        _fetch_descriptions(),
        *perm_tasks,
        *staff_tasks,
    )

    names_data = results[0]
    descriptions_data = results[1]

    n = len(artifacts)
    perm_contexts = results[2 : 2 + n]
    staff_counts = results[2 + n : 2 + 2 * n]

    # Build lookup maps
    name_map = {n.id: n for n in names_data}
    description_map = {d.id: d for d in descriptions_data}

    # ── Step 5: Build department list with permissions ──────────────────

    departments: list[ListDepartmentApiDepartment] = []

    for i, a in enumerate(artifacts):
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        desc_obj = (
            description_map.get(a.description_ids[0]) if a.description_ids else None
        )

        perm_ctx = perm_contexts[i]
        total_usage = perm_ctx.usage_count
        staff_count = staff_counts[i]

        is_inactive = not a.active

        can_edit = compute_can_edit(
            user_role=user_role,
            usage_count=total_usage,
        )
        can_delete = compute_can_delete(
            user_role=user_role,
            total_usage=total_usage,
        )
        can_duplicate = compute_can_duplicate(user_role=user_role)

        departments.append(
            ListDepartmentApiDepartment(
                department_id=a.id,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                staff_count=staff_count,
                is_inactive=is_inactive,
                can_edit=can_edit,
                can_duplicate=can_duplicate,
                can_delete=can_delete,
                updated_at=a.updated_at,
            )
        )

    return ListDepartmentApiResponse(
        actor_name=actor_name,
        departments=departments,
        total_count=total_count,
    )


# ── Helpers ────────────────────────────────────────────────────────────


def _empty_response(
    actor_name: str | None = None, total_count: int = 0
) -> ListDepartmentApiResponse:
    return ListDepartmentApiResponse(
        actor_name=actor_name,
        departments=[],
        total_count=total_count,
    )


async def _empty_list() -> list:
    return []


async def _staff_count_for_department(
    conn: asyncpg.Connection,
    department_resource_ids: list[UUID] | None,
) -> int:
    """Count profiles linked to a department via its departments_resource IDs."""
    if not department_resource_ids:
        return 0

    # search_profiles returns (ids, total_count) — total_count is the staff count
    _, total = await search_profile_artifacts(
        conn,
        department_ids=department_resource_ids,
        limit_count=1,
        offset_count=0,
    )
    return total
