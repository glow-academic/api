"""Persona search logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments, name)
  2. Reverse lookups — scenario_ids → personas_resource IDs
  3. search_personas — core artifact search (IDs + total_count)
  4. get_personas — hydrate junction IDs
  5. Resource get tools — hydrate names, descriptions, colors, icons
  6. Permissions — compute per-persona can_edit, can_delete, can_duplicate
  7. Facets — parallel resource/artifact searches for filter options
  8. search_profile_personas — num_profiles per persona
"""

from __future__ import annotations

import asyncio
from collections import Counter
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.persona.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.persona.types import (
    ImportField,
    ListPersonaApiPersona,
    ListPersonaApiResponse,
)
from app.infra.v5_types import ListFilterOption, ListFilterSection
from app.tools.artifacts.persona.get import get_personas
from app.tools.artifacts.persona.search import search_personas
from app.tools.resources.colors.get import get_colors
from app.tools.resources.colors.search import search_colors
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.fields.search import search_fields
from app.tools.resources.icons.get import get_icons
from app.tools.resources.icons.search import search_icons
from app.tools.resources.instructions.search import search_instructions
from app.tools.resources.names.get import get_names
from app.tools.resources.profile_personas.search import (
    search_profile_personas,
)
from app.tools.resources.scenarios.get import get_scenarios
from app.tools.resources.scenarios.search import (
    search_scenarios as search_scenarios_resource,
)
from app.tools.resources.voices.search import search_voices

PERSONA_IMPORT_FIELDS: list[ImportField] = [
    ImportField(
        key="name",
        label="Name",
        required=True,
        example="Sarah the Nurse",
        description="The persona's display name",
    ),
    ImportField(
        key="description",
        label="Description",
        example="A nurse with 5 years of experience",
        description="Optional description",
    ),
    ImportField(
        key="color",
        label="Color",
        required=True,
        example="#FF5733",
        description="Hex color code for the persona card",
    ),
    ImportField(
        key="icon",
        label="Icon",
        required=True,
        example="brain",
        description="Icon name from the icon library",
    ),
    ImportField(
        key="instructions",
        label="Instructions",
        required=True,
        example="You are a nurse helping patients...",
        description="System instructions for AI behavior",
    ),
    ImportField(
        key="active_flag",
        label="Active",
        type="boolean",
        example="true",
        description="Whether the persona is active (true/false)",
    ),
    ImportField(
        key="departments",
        label="Departments",
        multi=True,
        example="Nursing, Medicine",
        description="Comma-separated department names",
    ),
    ImportField(
        key="parameter_fields",
        label="Parameter Fields",
        multi=True,
        example="Patient Age, Condition",
        description="Comma-separated parameter field names",
    ),
    ImportField(
        key="examples",
        label="Examples",
        multi=True,
        example="Example conversation 1",
        description="Comma-separated example texts",
    ),
    ImportField(
        key="voices",
        label="Voices",
        multi=True,
        example="Alloy",
        description="Comma-separated voice names",
    ),
]


async def search_persona_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Main filters
    search: str | None = None,
    scenario_ids: list[UUID] | None = None,
    field_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    # Facet search text
    scenario_search: str | None = None,
    field_search: str | None = None,
    department_search: str | None = None,
    color_search: str | None = None,
    icon_search: str | None = None,
    voice_search: str | None = None,
    instruction_search: str | None = None,
    # Pagination
    page_size: int = 12,
    page_offset: int = 0,
) -> ListPersonaApiResponse:
    """Persona search using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, departments, name
      2. Reverse lookups (scenario_ids → personas_resource IDs)
      3. search_personas → (persona_artifact_ids, total_count)
      4. get_personas → hydrate junction IDs
      5. Parallel: hydrate resources + compute permissions + facets + num_profiles
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
    user_department_ids = profile.department_ids
    actor_name = profile.name

    # ── Step 2: Reverse lookups ────────────────────────────────────────

    personas_resource_ids: list[UUID] | None = None

    async with pool.acquire() as conn:
        if scenario_ids:
            # scenarios_resource has persona_ids (personas_resource IDs) denormalized
            scenarios = await get_scenarios(conn, scenario_ids, redis)
            pids: set[UUID] = set()
            for s in scenarios:
                pids.update(s.persona_ids)
            if pids:
                personas_resource_ids = list(pids)
            else:
                # No personas linked to these scenarios — empty result
                return _empty_response(actor_name)

        # field_ids are parameter_fields_resource IDs — direct junction filter
        parameter_field_ids = field_ids

        # ── Step 3: Search personas ────────────────────────────────────────

        persona_ids, total_count = await search_personas(
            conn,
            search=search,
            department_ids=filter_department_ids,
            parameter_field_ids=parameter_field_ids,
            persona_ids=personas_resource_ids,
            limit_count=page_size,
            offset_count=page_offset,
        )

        if not persona_ids:
            return _empty_response(actor_name, total_count=0)

        # ── Step 4: Get persona artifacts with junction IDs ────────────────

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
        )

    # ── Step 5: Parallel hydration + facets ────────────────────────────

    # Collect all resource IDs to hydrate
    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_color_ids: list[UUID] = []
    all_icon_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_color_ids.extend(a.color_ids or [])
        all_icon_ids.extend(a.icon_ids or [])

    # Parallel: hydrate resources + facets + num_profiles
    # Each branch acquires its own connection from the pool.

    async def _get_names() -> list:
        if not all_name_ids:
            return []
        async with pool.acquire() as conn:
            return await get_names(conn, all_name_ids, redis)

    async def _get_descriptions() -> list:
        if not all_description_ids:
            return []
        async with pool.acquire() as conn:
            return await get_descriptions(conn, all_description_ids, redis)

    async def _get_colors() -> list:
        if not all_color_ids:
            return []
        async with pool.acquire() as conn:
            return await get_colors(conn, all_color_ids, redis)

    async def _get_icons() -> list:
        if not all_icon_ids:
            return []
        async with pool.acquire() as conn:
            return await get_icons(conn, all_icon_ids, redis)

    async def _get_profile_persona_counts() -> dict[UUID, int]:
        return await _fetch_profile_persona_counts(pool, redis, artifacts)

    async def _get_scenario_facet() -> list:
        async with pool.acquire() as conn:
            return await search_scenarios_resource(
                conn, redis, search=scenario_search, scenario=True, limit_count=100
            )

    async def _get_field_facet() -> list:
        async with pool.acquire() as conn:
            return await search_fields(
                conn, redis, search=field_search, parameter=True, limit_count=100
            )

    async def _get_department_facet() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn, redis, search=department_search, persona=True, limit_count=100
            )

    async def _get_color_facet() -> list:
        async with pool.acquire() as conn:
            return await search_colors(
                conn, redis, search=color_search, persona=True, limit_count=100
            )

    async def _get_icon_facet() -> list:
        async with pool.acquire() as conn:
            return await search_icons(
                conn, redis, search=icon_search, persona=True, limit_count=100
            )

    async def _get_voice_facet() -> list:
        async with pool.acquire() as conn:
            return await search_voices(
                conn, redis, search=voice_search, persona=True, limit_count=100
            )

    async def _get_instruction_facet() -> list:
        async with pool.acquire() as conn:
            return await search_instructions(
                conn,
                redis,
                search=instruction_search,
                persona=True,
                limit_count=100,
            )

    (
        names_data,
        descriptions_data,
        colors_data,
        icons_data,
        profile_personas_data,
        scenario_facet,
        field_facet,
        department_facet,
        color_facet,
        icon_facet,
        voice_facet,
        instruction_facet,
    ) = await asyncio.gather(
        _get_names(),
        _get_descriptions(),
        _get_colors(),
        _get_icons(),
        _get_profile_persona_counts(),
        _get_scenario_facet(),
        _get_field_facet(),
        _get_department_facet(),
        _get_color_facet(),
        _get_icon_facet(),
        _get_voice_facet(),
        _get_instruction_facet(),
    )

    # Build lookup maps
    name_map = {n.id: n for n in names_data}
    description_map = {d.id: d for d in descriptions_data}
    color_map = {c.id: c for c in colors_data}
    icon_map = {i.id: i for i in icons_data}

    # ── Step 6: Build persona list with permissions ────────────────────

    personas: list[ListPersonaApiPersona] = []

    for a in artifacts:
        # Resolve first resource for display
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        desc_obj = (
            description_map.get(a.description_ids[0]) if a.description_ids else None
        )
        color_obj = color_map.get(a.color_ids[0]) if a.color_ids else None
        icon_obj = icon_map.get(a.icon_ids[0]) if a.icon_ids else None

        dept_ids_str = [str(d) for d in (a.department_ids or [])]

        # Count scenarios from facet data that reference this persona's personas_resource
        persona_resource_set = set(a.persona_ids or [])
        num_scenarios = sum(
            1 for s in scenario_facet if persona_resource_set & set(s.persona_ids or [])
        )

        num_profiles = profile_personas_data.get(a.id, 0)

        is_inactive = not a.active

        can_edit = compute_can_edit(
            user_role=user_role,
            persona_department_ids=dept_ids_str,
            active_scenario_count=num_scenarios,
            user_department_ids=user_department_ids,
        )
        can_delete = compute_can_delete(
            user_role=user_role,
            persona_department_ids=dept_ids_str,
            active_scenario_count=num_scenarios,
        )
        can_duplicate = compute_can_duplicate(user_role)

        personas.append(
            ListPersonaApiPersona(
                persona_id=a.id,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                color=color_obj.hex_code if color_obj else None,
                icon=icon_obj.value if icon_obj else None,
                department_ids=dept_ids_str,
                scenario_ids=None,
                field_ids=[str(f) for f in (a.parameter_field_ids or [])],
                is_inactive=is_inactive,
                generated=a.generated,
                mcp=a.mcp,
                num_scenarios=num_scenarios,
                num_profiles=num_profiles,
                can_edit=can_edit,
                can_duplicate=can_duplicate,
                can_delete=can_delete,
                updated_at=a.updated_at,
            )
        )

    # ── Step 7: Build facet sections ───────────────────────────────────

    scenario_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(s.id), name=s.name, count=0) for s in scenario_facet
        ],
        selected_ids=[str(sid) for sid in scenario_ids] if scenario_ids else None,
        search=scenario_search,
    )

    field_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(f.id), name=f.name, count=0) for f in field_facet
        ],
        selected_ids=[str(fid) for fid in field_ids] if field_ids else None,
        search=field_search,
    )

    department_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(d.id), name=d.name, count=0)
            for d in department_facet
        ],
        selected_ids=[str(did) for did in filter_department_ids]
        if filter_department_ids
        else None,
        search=department_search,
    )

    color_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(c.id), name=c.name, hex_code=c.hex_code, count=0)
            for c in color_facet
        ],
        search=color_search,
    )

    icon_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(i.id), name=i.name, value=i.value, count=0)
            for i in icon_facet
        ],
        search=icon_search,
    )

    voice_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(v.id), name=v.voice, count=0) for v in voice_facet
        ],
        search=voice_search,
    )

    instruction_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(i.id), name=i.template, count=0)
            for i in instruction_facet
        ],
        search=instruction_search,
    )

    return ListPersonaApiResponse(
        actor_name=actor_name,
        personas=personas,
        scenario_filter=scenario_filter,
        field_filter=field_filter,
        department_filter=department_filter,
        color_filter=color_filter,
        icon_filter=icon_filter,
        voice_filter=voice_filter,
        instruction_filter=instruction_filter,
        total_count=total_count,
    )


# ── Helpers ────────────────────────────────────────────────────────────


def _empty_response(
    actor_name: str | None = None, total_count: int = 0
) -> ListPersonaApiResponse:
    return ListPersonaApiResponse(
        actor_name=actor_name,
        personas=[],
        total_count=total_count,
    )


async def _empty_list() -> list:
    return []


async def _fetch_profile_persona_counts(
    pool: asyncpg.Pool,
    redis: Redis,
    artifacts: list,
) -> dict[UUID, int]:
    """Count num_profiles per persona artifact via profile_personas resource."""
    # Collect all personas_resource IDs and map back to artifact IDs
    resource_to_artifact: dict[UUID, UUID] = {}
    all_persona_resource_ids: list[UUID] = []
    for a in artifacts:
        for pid in a.persona_ids or []:
            resource_to_artifact[pid] = a.id
            all_persona_resource_ids.append(pid)

    if not all_persona_resource_ids:
        return {}

    async with pool.acquire() as conn:
        profile_personas = await search_profile_personas(
            conn,
            redis,
            persona_ids=all_persona_resource_ids,
            limit_count=1000,
        )

    # Count per artifact
    counts: Counter[UUID] = Counter()
    for pp in profile_personas:
        artifact_id = resource_to_artifact.get(pp.persona_id)
        if artifact_id:
            counts[artifact_id] += 1

    return dict(counts)
