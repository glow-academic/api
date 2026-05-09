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

from app.infra.api_types import ListFilterOption, ListFilterSection
from app.infra.department.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.department.permissions_context import (
    DepartmentPermissionsContext,
    resolve_department_permissions_context,
)
from app.infra.department.types import (
    ListDepartmentApiDepartment,
    ListDepartmentApiResponse,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.department.get import get_departments
from app.tools.artifacts.department.search import (
    search_departments as search_department_artifacts,
)
from app.tools.artifacts.profile.search import (
    search_profiles as search_profile_artifacts,
)
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.get import get_names
from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

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
    search: str | None = None,
    flag_search: str | None = None,
    page_size: int = 12,
    page_offset: int = 0,
    bypass_cache: bool = False,
    **_kwargs,
) -> ListDepartmentApiResponse:
    """department search — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("department/search", {
            "profile_id": str(profile_id),
            "search": search,
            "flag_search": flag_search,
            "page_size": page_size,
            "page_offset": page_offset,
        }),
        tags=["search", "department", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ListDepartmentApiResponse,
        builder=lambda: _search_department_build(
            pool, redis,
            profile_id=profile_id,
            search=search,
            flag_search=flag_search,
            page_size=page_size,
            page_offset=page_offset,
        ),
        bypass_cache=bypass_cache,
    )


async def _search_department_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Main filters
    search: str | None = None,
    # Facet search text
    flag_search: str | None = None,
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

    user_role_level = profile.role_level
    actor_name = profile.name

    # ── Step 2: Search departments ─────────────────────────────────────

    async with pool.acquire() as conn:
        department_ids, total_count = await search_department_artifacts(
            conn,
            search=search,
            limit_count=page_size,
            offset_count=page_offset,
        )

    # Pending ledger entries — see project_soft_calls_entry_pattern.
    from app.tools.entries.soft_calls.search import search_soft_calls
    async with pool.acquire() as conn:
        pending_entries = await search_soft_calls(
            conn, artifact="department", status="pending", limit=1000,
        )
    pending_ledger_ids = [e.artifact_id for e in pending_entries]
    ledger_by_artifact_id = {e.artifact_id: e for e in pending_entries}

    merged_ids: list[UUID] = []
    seen: set[UUID] = set()
    for did in [*department_ids, *pending_ledger_ids]:
        if did in seen:
            continue
        seen.add(did)
        merged_ids.append(did)
    added = sum(1 for did in pending_ledger_ids if did not in set(department_ids))
    total_count = total_count + added

    if not merged_ids:
        return _empty_response(actor_name, total_count=0)

    # ── Step 3: Get department artifacts with junction IDs ─────────────

    async with pool.acquire() as conn:
        artifacts = await get_departments(
            conn,
            merged_ids,
            names=True,
            descriptions=True,
            flags=True,
            departments=True,
            active=None,
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
        return await get_names(pool, all_name_ids, redis)

    async def _fetch_descriptions() -> list:
        if not all_description_ids:
            return []
        return await get_descriptions(pool, all_description_ids, redis)

    # Build per-dept-resource maps for profile/setting/login junctions.
    # All queries are batched on the union of dept resource ids across artifacts.
    all_dept_resource_ids: list[UUID] = []
    for a in artifacts:
        all_dept_resource_ids.extend(a.department_ids or [])

    profiles_by_dept_resource: dict[UUID, list[UUID]] = {}
    settings_by_dept_resource: dict[UUID, list[UUID]] = {}
    logins_by_setting: dict[UUID, list[UUID]] = {}

    if all_dept_resource_ids:
        async with pool.acquire() as conn:
            prof_rows = await conn.fetch(
                """
                SELECT departments_id,
                       ARRAY_AGG(DISTINCT profile_id)
                         FILTER (WHERE profile_id IS NOT NULL) AS profile_ids
                FROM profile_departments_junction
                WHERE departments_id = ANY($1) AND active = true
                GROUP BY departments_id
                """,
                all_dept_resource_ids,
            )
            set_rows = await conn.fetch(
                """
                SELECT departments_id,
                       ARRAY_AGG(DISTINCT setting_id)
                         FILTER (WHERE setting_id IS NOT NULL) AS setting_ids
                FROM setting_departments_junction
                WHERE departments_id = ANY($1) AND active = true
                GROUP BY departments_id
                """,
                all_dept_resource_ids,
            )
        for r in prof_rows:
            profiles_by_dept_resource[r["departments_id"]] = list(
                r["profile_ids"] or []
            )
        for r in set_rows:
            settings_by_dept_resource[r["departments_id"]] = list(
                r["setting_ids"] or []
            )

        # Hop 2: from the discovered setting_ids, fetch logins_resource ids.
        all_setting_ids: list[UUID] = []
        for sids in settings_by_dept_resource.values():
            all_setting_ids.extend(sids)
        if all_setting_ids:
            async with pool.acquire() as conn:
                login_rows = await conn.fetch(
                    """
                    SELECT setting_id,
                           ARRAY_AGG(DISTINCT logins_id)
                             FILTER (WHERE logins_id IS NOT NULL) AS login_ids
                    FROM setting_logins_junction
                    WHERE setting_id = ANY($1) AND active = true
                    GROUP BY setting_id
                    """,
                    all_setting_ids,
                )
            for r in login_rows:
                logins_by_setting[r["setting_id"]] = list(r["login_ids"] or [])

    # Per-department: resolve permissions context + staff count
    # permissions_context gives us usage_count
    # search_profiles with department_ids gives us staff_count via total_count

    async def _fetch_perm(artifact_id: UUID) -> DepartmentPermissionsContext:
        async with pool.acquire() as conn:
            return await resolve_department_permissions_context(conn, artifact_id)

    async def _fetch_staff(dept_ids: list[UUID] | None) -> int:
        async with pool.acquire() as conn:
            return await _staff_count_for_department(conn, dept_ids)

    async def _fetch_flag_facet() -> list:
        async with pool.acquire() as conn:
            return await search_flags(
                conn, redis, search=flag_search, department=True, limit_count=100
            )

    perm_tasks = [_fetch_perm(a.id) for a in artifacts]
    staff_tasks = [_fetch_staff(a.department_ids) for a in artifacts]

    # Gather all
    results = await asyncio.gather(
        _fetch_names(),
        _fetch_descriptions(),
        _fetch_flag_facet(),
        *perm_tasks,
        *staff_tasks,
    )

    names_data = results[0]
    descriptions_data = results[1]
    flag_facet = results[2]

    n = len(artifacts)
    perm_contexts = results[3 : 3 + n]
    staff_counts = results[3 + n : 3 + 2 * n]

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
            role_level=user_role_level, role_permissions=profile.role_permissions,
            usage_count=total_usage,
        )
        can_delete = compute_can_delete(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            total_usage=total_usage,
        )
        can_duplicate = compute_can_duplicate(role_level=user_role_level, role_permissions=profile.role_permissions)

        # Aggregate profile/setting/login ids across this dept's resource rows.
        dept_profile_ids: list[UUID] = []
        dept_setting_ids: list[UUID] = []
        dept_login_ids: list[UUID] = []
        seen_p: set[UUID] = set()
        seen_s: set[UUID] = set()
        seen_l: set[UUID] = set()
        for dr_id in a.department_ids or []:
            for pid in profiles_by_dept_resource.get(dr_id, []):
                if pid not in seen_p:
                    seen_p.add(pid)
                    dept_profile_ids.append(pid)
            for sid in settings_by_dept_resource.get(dr_id, []):
                if sid not in seen_s:
                    seen_s.add(sid)
                    dept_setting_ids.append(sid)
                for lid in logins_by_setting.get(sid, []):
                    if lid not in seen_l:
                        seen_l.add(lid)
                        dept_login_ids.append(lid)

        ledger = ledger_by_artifact_id.get(a.id)
        departments.append(
            ListDepartmentApiDepartment(
                department_id=a.id,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                staff_count=staff_count,
                profile_ids=dept_profile_ids,
                setting_ids=dept_setting_ids,
                login_ids=dept_login_ids,
                is_inactive=is_inactive,
                can_edit=can_edit,
                can_duplicate=can_duplicate,
                can_delete=can_delete,
                updated_at=a.updated_at,
                pending_status=ledger.status if ledger else None,
                pending_operation=ledger.operation if ledger else None,
                pending_call_id=ledger.call_id if ledger else None,
            )
        )

    flag_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(f.id), name=f.name, type=f.type, count=0)
            for f in flag_facet
        ],
        search=flag_search,
    )

    return ListDepartmentApiResponse(
        actor_name=actor_name,
        departments=departments,
        flag_filter=flag_filter,
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
