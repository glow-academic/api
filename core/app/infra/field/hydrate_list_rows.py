"""Hydrate ``ListFieldApiField`` rows for a specific set of field ids.

Used by create/duplicate/update impls to return the full row content
alongside their per-row status results — so the client's ghost rail can
materialize the new/changed row directly from the audit ``.completed``
payload, no ``router.refresh()`` needed (which would re-burst the page's
SSR fetches).

This is a focused subset of ``_search_field_build``'s flow: the row
hydration steps (get artifacts → resolve junctions → hydrate names /
descriptions → compute permissions), without the facet aggregation,
pagination, or big-cache wrap that the search route layers on top.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.field.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.field.permissions_context import resolve_field_permissions_context
from app.infra.field.types import ListFieldApiField
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.field.get import get_fields
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.names.get import get_names


async def hydrate_field_list_rows(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    field_ids: list[UUID],
) -> list[ListFieldApiField]:
    """Return ``ListFieldApiField`` rows for the given field ids.

    Mirrors ``_search_field_build``'s row-hydration steps minus facets
    and pagination. Permissions are computed per-row using the same
    ``resolve_field_permissions_context`` helper the search path uses,
    so ``can_edit`` / ``can_delete`` / ``can_duplicate`` reflect the
    current actor's role + the field's active-parameter count.
    """
    if not field_ids:
        return []

    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        return []

    user_role_level = profile.role_level
    user_department_ids = profile.department_ids

    async with pool.acquire() as conn:
        artifacts = await get_fields(
            conn,
            field_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            conditional_parameters=True,
            fields=True,
            active=None,
        )

        from app.tools.entries.soft_calls.search import search_soft_calls
        ledger_entries = await search_soft_calls(
            conn, artifact="field", artifact_ids=field_ids,
            limit=len(field_ids) or 1,
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

    async def _names() -> list:
        return await get_names(pool, all_name_ids, redis) if all_name_ids else []

    async def _descs() -> list:
        return (
            await get_descriptions(pool, all_description_ids, redis)
            if all_description_ids
            else []
        )

    async def _perm(artifact_id: UUID) -> object:
        async with pool.acquire() as conn:
            return await resolve_field_permissions_context(conn, artifact_id)

    perm_tasks = [_perm(a.id) for a in artifacts]

    names_data, descriptions_data, *perm_results = await asyncio.gather(
        _names(), _descs(), *perm_tasks,
    )

    name_map = {n.id: n for n in names_data}
    description_map = {d.id: d for d in descriptions_data}

    rows: list[ListFieldApiField] = []
    for i, a in enumerate(artifacts):
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        desc_obj = description_map.get(a.description_ids[0]) if a.description_ids else None

        dept_ids_str = [str(d) for d in (a.department_ids or [])]
        active_param_count = perm_results[i].active_parameter_count

        is_inactive = not a.active

        can_edit = compute_can_edit(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            field_department_ids=dept_ids_str,
            active_parameter_count=active_param_count,
            user_department_ids=user_department_ids,
        )
        can_delete = compute_can_delete(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            field_department_ids=dept_ids_str,
            active_parameter_count=active_param_count,
        )
        can_duplicate = compute_can_duplicate(
            role_level=user_role_level, role_permissions=profile.role_permissions,
        )

        ledger = ledger_by_artifact_id.get(a.id)
        rows.append(
            ListFieldApiField(
                field_id=a.id,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                department_ids=dept_ids_str,
                conditional_parameter_ids=a.conditional_parameter_ids,
                persona_ids=None,
                is_inactive=is_inactive,
                pending_status=ledger.status if ledger else None,
                pending_operation=ledger.operation if ledger else None,
                pending_call_id=ledger.call_id if ledger else None,
                can_edit=can_edit,
                can_duplicate=can_duplicate,
                can_delete=can_delete,
                updated_at=a.updated_at,
            )
        )

    return rows
