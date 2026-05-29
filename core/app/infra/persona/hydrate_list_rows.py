"""Hydrate `ListPersonaApiPersona` rows for a specific set of persona ids.

Used by create/duplicate/update impls to return the full row content
alongside their per-row status results — so the client's ghost rail can
materialize the new/changed row directly from the audit ``.completed``
payload, no ``router.refresh()`` needed (which would re-burst the page's
SSR fetches).

This is a focused subset of ``search_persona_impl``'s flow: the row
hydration steps (get artifacts → resolve junctions → hydrate resources
→ compute permissions), without the facet aggregation, pagination, or
big-cache wrap that the search route layers on top.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.persona.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.persona.types import ListPersonaApiPersona
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.persona.get import get_personas
from app.tools.resources.colors.get import get_colors
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.icons.get import get_icons
from app.tools.resources.names.get import get_names
from app.tools.resources.scenarios.search import search_scenarios as search_scenarios_resource


async def hydrate_persona_list_rows(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    persona_ids: list[UUID],
) -> list[ListPersonaApiPersona]:
    """Return ``ListPersonaApiPersona`` rows for the given persona ids.

    Mirrors ``_search_persona_build``'s row-hydration steps minus facets
    and pagination. ``num_profiles`` is reported as 0 (the persona is
    brand-new or just edited; profile interaction count is server-side
    materialized and reconciles on next page-level search). Scenario
    count is computed from the same scenario facet ``/persona/search``
    uses, so it's accurate for both fresh and updated rows.
    """
    if not persona_ids:
        return []

    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        return []

    user_role_level = profile.role_level
    user_department_ids = profile.department_ids

    async with pool.acquire() as conn:
        # ``active=None`` so dormant pending creates/duplicates resolve too.
        artifacts = await get_personas(
            conn,
            persona_ids,
            names=True,
            descriptions=True,
            colors=True,
            icons=True,
            departments=True,
            flags=True,
            parameter_fields=True,
            personas=True,
            active=None,
        )

        # Latest ledger row per artifact_id — same black box the search
        # endpoint uses, so the live ghost cards render with parity.
        from app.tools.entries.soft_calls.search import search_soft_calls
        ledger_entries = await search_soft_calls(
            conn, redis, artifact="persona", artifact_ids=persona_ids,
            limit=len(persona_ids) or 1,
        )
    ledger_by_artifact_id = {e.artifact_id: e for e in ledger_entries}

    if not artifacts:
        return []

    # Collect resource ids to hydrate in parallel.
    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_color_ids: list[UUID] = []
    all_icon_ids: list[UUID] = []
    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_color_ids.extend(a.color_ids or [])
        all_icon_ids.extend(a.icon_ids or [])

    async def _names() -> list:
        return await get_names(pool, all_name_ids, redis) if all_name_ids else []

    async def _descs() -> list:
        return await get_descriptions(pool, all_description_ids, redis) if all_description_ids else []

    async def _colors() -> list:
        return await get_colors(pool, all_color_ids, redis) if all_color_ids else []

    async def _icons() -> list:
        return await get_icons(pool, all_icon_ids, redis) if all_icon_ids else []

    async def _scenarios_facet() -> list:
        # Used only to compute num_scenarios per row — the same facet
        # ``/persona/search`` queries. Capped at 100 (matches search).
        async with pool.acquire() as conn:
            return await search_scenarios_resource(
                conn, redis, scenario=True, limit_count=100,
            )

    names_data, descriptions_data, colors_data, icons_data, scenario_facet = (
        await asyncio.gather(
            _names(), _descs(), _colors(), _icons(), _scenarios_facet(),
        )
    )

    name_map = {n.id: n for n in names_data}
    description_map = {d.id: d for d in descriptions_data}
    color_map = {c.id: c for c in colors_data}
    icon_map = {i.id: i for i in icons_data}

    rows: list[ListPersonaApiPersona] = []
    for a in artifacts:
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        desc_obj = description_map.get(a.description_ids[0]) if a.description_ids else None
        color_obj = color_map.get(a.color_ids[0]) if a.color_ids else None
        icon_obj = icon_map.get(a.icon_ids[0]) if a.icon_ids else None

        dept_ids_str = [str(d) for d in (a.department_ids or [])]

        persona_resource_set = set(a.persona_ids or [])
        num_scenarios = sum(
            1 for s in scenario_facet if persona_resource_set & set(s.persona_ids or [])
        )

        is_inactive = not a.active

        can_edit = compute_can_edit(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            persona_department_ids=dept_ids_str,
            active_scenario_count=num_scenarios,
            user_department_ids=user_department_ids,
        )
        can_delete = compute_can_delete(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            persona_department_ids=dept_ids_str,
            active_scenario_count=num_scenarios,
        )
        can_duplicate = compute_can_duplicate(
            role_level=user_role_level, role_permissions=profile.role_permissions,
        )

        ledger = ledger_by_artifact_id.get(a.id)
        rows.append(
            ListPersonaApiPersona(
                id=a.id,

                persona_id=a.id,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                color=color_obj.hex_code if color_obj else None,
                icon=icon_obj.value if icon_obj else None,
                department_ids=dept_ids_str,
                scenario_ids=None,
                field_ids=[str(f) for f in (a.parameter_field_ids or [])],
                is_inactive=is_inactive,
                pending_status=ledger.status if ledger else None,
                pending_operation=ledger.operation if ledger else None,
                pending_call_id=ledger.call_id if ledger else None,
                generated=a.generated,
                mcp=a.mcp,
                num_scenarios=num_scenarios,
                num_profiles=0,  # Reconciled on next page-level search.
                can_edit=can_edit,
                can_duplicate=can_duplicate,
                can_delete=can_delete,
                updated_at=a.updated_at,
            )
        )

    return rows
