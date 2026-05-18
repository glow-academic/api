"""Hydrate ``ListParameterApiParameter`` rows for a specific set of parameter ids.

Used by create/duplicate/update impls to return the full row content
alongside their per-row status results — so the client's ghost rail can
materialize the new/changed row directly from the audit ``.completed``
payload, no ``router.refresh()`` needed (which would re-burst the page's
SSR fetches).

This is a focused subset of ``_search_parameter_build``'s flow: the row
hydration steps (get artifacts → resolve junctions → hydrate names /
descriptions / sample-item field names → compute permissions), without
the facet aggregation, pagination, or big-cache wrap that the search
route layers on top.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.parameter.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.parameter.permissions_context import (
    resolve_parameter_permissions_context,
)
from app.infra.parameter.types import ListParameterApiParameter
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.parameter.get import get_parameters
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.fields.get import get_fields as get_fields_resource
from app.tools.resources.names.get import get_names
from app.tools.resources.parameter_fields.get import get_parameter_fields


async def hydrate_parameter_list_rows(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    parameter_ids: list[UUID],
) -> list[ListParameterApiParameter]:
    """Return ``ListParameterApiParameter`` rows for the given parameter ids.

    Mirrors ``_search_parameter_build``'s row-hydration steps minus
    facets and pagination. ``active_scenario_count`` is computed via
    the same per-parameter permissions context the search route uses,
    so ``can_edit`` / ``can_delete`` stay accurate for both fresh and
    updated rows.
    """
    if not parameter_ids:
        return []

    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        return []

    user_role_level = profile.role_level
    user_department_ids = profile.department_ids

    async with pool.acquire() as conn:
        artifacts = await get_parameters(
            conn,
            parameter_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            fields=True,
            parameters=True,
            active=None,
        )

        from app.tools.entries.soft_calls.search import search_soft_calls
        ledger_entries = await search_soft_calls(
            conn, artifact="parameter", artifact_ids=parameter_ids,
            limit=len(parameter_ids) or 1,
        )
    ledger_by_artifact_id = {e.artifact_id: e for e in ledger_entries}

    if not artifacts:
        return []

    # Collect resource ids to hydrate in parallel.
    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_field_junction_ids: list[UUID] = []
    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_field_junction_ids.extend(a.field_ids or [])

    async def _names() -> list:
        return await get_names(pool, all_name_ids, redis) if all_name_ids else []

    async def _descs() -> list:
        return (
            await get_descriptions(pool, all_description_ids, redis)
            if all_description_ids
            else []
        )

    async def _parameter_fields() -> list:
        return (
            await get_parameter_fields(pool, all_field_junction_ids, redis)
            if all_field_junction_ids
            else []
        )

    async def _get_perm(artifact_id: UUID):
        async with pool.acquire() as conn:
            return await resolve_parameter_permissions_context(conn, artifact_id)

    perm_tasks = [_get_perm(a.id) for a in artifacts]

    names_data, descriptions_data, parameter_fields_data, *perm_results = (
        await asyncio.gather(_names(), _descs(), _parameter_fields(), *perm_tasks)
    )

    # Hydrate field names for sample_items — same shape as search.
    all_fields_resource_ids = list({pf.field_id for pf in parameter_fields_data})
    async with pool.acquire() as conn:
        fields_resource_data = (
            await get_fields_resource(conn, all_fields_resource_ids, redis)
            if all_fields_resource_ids
            else []
        )
    field_name_map: dict[UUID, str] = {f.id: f.name for f in fields_resource_data}
    pf_id_to_name: dict[UUID, str] = {}
    for pf in parameter_fields_data:
        name = field_name_map.get(pf.field_id)
        if name:
            pf_id_to_name[pf.id] = name

    name_map = {n.id: n for n in names_data}
    description_map = {d.id: d for d in descriptions_data}

    rows: list[ListParameterApiParameter] = []
    for i, a in enumerate(artifacts):
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        desc_obj = (
            description_map.get(a.description_ids[0]) if a.description_ids else None
        )

        dept_ids_str = [str(d) for d in (a.department_ids or [])]
        active_scenario_count = perm_results[i].active_scenario_count

        can_edit = compute_can_edit(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            parameter_department_ids=dept_ids_str,
            active_scenario_count=active_scenario_count,
            user_department_ids=user_department_ids,
        )
        can_delete = compute_can_delete(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            parameter_department_ids=dept_ids_str,
            active_scenario_count=active_scenario_count,
        )
        can_duplicate = compute_can_duplicate(
            role_level=user_role_level, role_permissions=profile.role_permissions,
        )

        ledger = ledger_by_artifact_id.get(a.id)
        rows.append(
            ListParameterApiParameter(
                parameter_id=a.id,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                active=a.active,
                is_inactive=not a.active,
                department_ids=dept_ids_str,
                scenario_ids=None,
                num_items=len(a.field_ids or []),
                sample_items=[
                    pf_id_to_name[fid]
                    for fid in (a.field_ids or [])[:3]
                    if fid in pf_id_to_name
                ],
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
