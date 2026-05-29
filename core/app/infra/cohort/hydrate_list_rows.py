"""Hydrate ``ListCohortApiCohort`` rows for a specific set of cohort ids.

Used by create/duplicate/update impls to return the full row content
alongside their per-row status results — so the client's ghost rail can
materialize the new/changed row directly from the audit ``.completed``
payload, no ``router.refresh()`` needed (which would re-burst the page's
SSR fetches).

This is a focused subset of ``_search_cohort_build``'s flow: the row
hydration steps (get artifacts → resolve junctions → hydrate names →
compute permissions), without the facet aggregation, pagination, or
big-cache wrap that the search route layers on top.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.cohort.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
    compute_can_leave,
)
from app.infra.cohort.types import ListCohortApiCohort
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.cohort.get import get_cohorts
from app.tools.resources.names.get import get_names


async def hydrate_cohort_list_rows(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    cohort_ids: list[UUID],
) -> list[ListCohortApiCohort]:
    """Return ``ListCohortApiCohort`` rows for the given cohort ids.

    Mirrors ``_search_cohort_build``'s row-hydration steps minus facets
    and pagination. Description is left as None (the list endpoint also
    returns ``None`` — search has the same pattern; the description is
    only fetched on the cohort GET endpoint). ``usage_count`` and
    ``num_members`` are derived from the artifact's ``profiles_ids``
    junction so they stay accurate for both fresh and updated rows.
    """
    if not cohort_ids:
        return []

    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        return []

    user_role_level = profile.role_level
    user_department_ids = profile.department_ids
    user_profiles_id = profile.profiles_id

    async with pool.acquire() as conn:
        artifacts = await get_cohorts(
            conn,
            cohort_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            profiles=True,
            simulations=True,
            active=None,
        )

        from app.tools.entries.soft_calls.search import search_soft_calls
        ledger_entries = await search_soft_calls(
            conn, redis, artifact="cohort", artifact_ids=cohort_ids,
            limit=len(cohort_ids) or 1,
        )
    ledger_by_artifact_id = {e.artifact_id: e for e in ledger_entries}

    if not artifacts:
        return []

    # Collect resource ids to hydrate.
    all_name_ids: list[UUID] = []
    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])

    names_data = await get_names(pool, all_name_ids, redis) if all_name_ids else []
    name_map = {n.id: n for n in names_data}

    rows: list[ListCohortApiCohort] = []
    for a in artifacts:
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        dept_ids_str = [str(d) for d in (a.department_ids or [])]
        profile_ids_str = [str(p) for p in (a.profiles_ids or [])]
        sim_ids_str = [str(s) for s in (a.simulation_ids or [])]

        is_member = user_profiles_id in set(a.profiles_ids or [])
        usage_count = len(a.profiles_ids or [])

        can_edit = compute_can_edit(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            cohort_department_ids=dept_ids_str,
            user_department_ids=user_department_ids,
        )
        can_delete = compute_can_delete(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            cohort_department_ids=dept_ids_str,
            usage_count=usage_count,
        )
        can_duplicate = compute_can_duplicate(
            role_level=user_role_level, role_permissions=profile.role_permissions,
        )
        can_leave = compute_can_leave(is_member=is_member)

        ledger = ledger_by_artifact_id.get(a.id)
        rows.append(
            ListCohortApiCohort(
                id=a.id,

                cohort_id=a.id,
                name=name_obj.name if name_obj else None,
                description=None,
                is_inactive=not a.active,
                generated=a.generated,
                mcp=a.mcp,
                department_ids=dept_ids_str,
                profile_ids=profile_ids_str,
                simulation_ids=sim_ids_str,
                usage_count=usage_count,
                num_members=usage_count,
                can_edit=can_edit,
                can_delete=can_delete,
                can_duplicate=can_duplicate,
                can_leave=can_leave,
                updated_at=a.updated_at,
                pending_status=ledger.status if ledger else None,
                pending_operation=ledger.operation if ledger else None,
                pending_call_id=ledger.call_id if ledger else None,
            )
        )

    return rows
