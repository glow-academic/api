"""Hydrate ``ListDepartmentApiDepartment`` rows for a specific set of department ids.

Used by create/duplicate/update impls to return the full row content
alongside their per-row status results — so the client's ghost rail can
materialize the new/changed row directly from the audit ``.completed``
payload, no ``router.refresh()`` needed (which would re-burst the page's
SSR fetches).

This is a focused subset of ``_search_department_build``'s flow: the
row hydration steps (get artifacts → resolve junctions → hydrate names
/ descriptions → compute permissions), without the facet aggregation,
pagination, or big-cache wrap that the search route layers on top.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.department.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.department.permissions_context import (
    resolve_department_permissions_context,
)
from app.infra.department.types import ListDepartmentApiDepartment
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.department.get import get_departments
from app.tools.artifacts.profile.search import (
    search_profiles as search_profile_artifacts,
)
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.names.get import get_names


async def hydrate_department_list_rows(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    department_ids: list[UUID],
) -> list[ListDepartmentApiDepartment]:
    """Return ``ListDepartmentApiDepartment`` rows for the given ids.

    Mirrors ``_search_department_build``'s row-hydration steps minus
    facets and pagination. ``staff_count`` is computed via the same
    ``search_profiles`` total_count the search endpoint uses, so it
    stays accurate for fresh and updated rows.
    """
    if not department_ids:
        return []

    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        return []

    user_role_level = profile.role_level

    async with pool.acquire() as conn:
        artifacts = await get_departments(
            conn,
            department_ids,
            names=True,
            descriptions=True,
            flags=True,
            departments=True,
            active=None,
        )

        from app.tools.entries.soft_calls.search import search_soft_calls
        ledger_entries = await search_soft_calls(
            conn, artifact="department", artifact_ids=department_ids,
            limit=len(department_ids) or 1,
        )
    ledger_by_artifact_id = {e.artifact_id: e for e in ledger_entries}

    if not artifacts:
        return []

    # Collect resource ids to hydrate in parallel.
    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])

    # Resolve junction maps for profile / setting / login ids per
    # departments_resource id (same as ``_search_department_build``).
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

    async def _names() -> list:
        return await get_names(pool, all_name_ids, redis) if all_name_ids else []

    async def _descs() -> list:
        return (
            await get_descriptions(pool, all_description_ids, redis)
            if all_description_ids
            else []
        )

    async def _fetch_perm(artifact_id: UUID):
        async with pool.acquire() as conn:
            return await resolve_department_permissions_context(conn, artifact_id)

    async def _fetch_staff(dept_resource_ids: list[UUID] | None) -> int:
        if not dept_resource_ids:
            return 0
        async with pool.acquire() as conn:
            _, total = await search_profile_artifacts(
                conn,
                department_ids=dept_resource_ids,
                limit_count=1,
                offset_count=0,
            )
        return total

    perm_tasks = [_fetch_perm(a.id) for a in artifacts]
    staff_tasks = [_fetch_staff(a.department_ids) for a in artifacts]

    results = await asyncio.gather(
        _names(), _descs(), *perm_tasks, *staff_tasks,
    )
    names_data = results[0]
    descriptions_data = results[1]
    n = len(artifacts)
    perm_contexts = results[2 : 2 + n]
    staff_counts = results[2 + n : 2 + 2 * n]

    name_map = {nm.id: nm for nm in names_data}
    description_map = {d.id: d for d in descriptions_data}

    rows: list[ListDepartmentApiDepartment] = []
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
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
            usage_count=total_usage,
        )
        can_delete = compute_can_delete(
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
            total_usage=total_usage,
        )
        can_duplicate = compute_can_duplicate(
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
        )

        # Aggregate profile/setting/login ids across this dept's
        # resource rows (mirrors search.py).
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
        rows.append(
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

    return rows
