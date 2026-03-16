"""Persona permissions context + shared save helpers.

Permissions context:
  1. resolve_persona_permissions_context — lightweight access + edit check

Shared save helpers (used by both create and update):
  2. resolve_persona_values — raw string → resource ID resolution
  3. create_denormalized_snapshot — hydrate IDs → personas_resource snapshot

Each parallel branch acquires its own connection from the pool.
Composes existing black-box fetchers — no raw SQL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.persona.get import (
    get_personas as get_persona_artifacts,
)
from app.tools.artifacts.scenario.search import search_scenarios
from app.tools.resources.colors.get import get_colors
from app.tools.resources.colors.search import search_colors
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.examples.create import create_example
from app.tools.resources.examples.get import get_examples
from app.tools.resources.fields.get import get_fields
from app.tools.resources.flags.search import search_flags
from app.tools.resources.icons.get import get_icons
from app.tools.resources.icons.search import search_icons
from app.tools.resources.instructions.create import create_instruction
from app.tools.resources.instructions.get import get_instructions
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.tools.resources.parameter_fields.search import (
    search_parameter_fields,
)
from app.tools.resources.personas.create import (
    create_persona as create_persona_resource,
)
from app.tools.resources.voices.search import search_voices

if TYPE_CHECKING:
    from app.infra.persona.create import CreatePersonaItem, PersonaFieldError
    from app.infra.persona.types import (
        UpdatePersonaItem,
    )


@dataclass(frozen=True)
class PersonaPermissionsContext:
    """Lightweight context for persona permission checks."""

    exists: bool
    department_ids: list[UUID]
    active_scenario_count: int


async def resolve_persona_permissions_context(
    pool: asyncpg.Pool,
    persona_id: UUID,
) -> PersonaPermissionsContext:
    """Fetch just what's needed for persona permission checks.

    Two black-box tool calls (sequential — no gather needed):
      1. get_persona_artifacts → department_ids + persona_ids (resource IDs)
      2. search_scenarios → any active scenarios using this persona?
    """
    async with pool.acquire() as conn:
        artifacts = await get_persona_artifacts(
            conn,
            [persona_id],
            departments=True,
            personas=True,
        )

    if not artifacts:
        return PersonaPermissionsContext(
            exists=False,
            department_ids=[],
            active_scenario_count=0,
        )

    artifact = artifacts[0]
    department_ids = list(artifact.department_ids or [])
    personas_resource_ids = list(artifact.persona_ids or [])

    if personas_resource_ids:
        async with pool.acquire() as conn:
            _, total = await search_scenarios(
                conn,
                persona_ids=personas_resource_ids,
                active_only=True,
                limit_count=1,
            )
    else:
        total = 0

    return PersonaPermissionsContext(
        exists=True,
        department_ids=department_ids,
        active_scenario_count=total,
    )


# ---------------------------------------------------------------------------
# Shared save helpers — used by both persona_create and persona_update
# ---------------------------------------------------------------------------


async def resolve_persona_values(
    pool: asyncpg.Pool,
    redis: Redis,
    item: CreatePersonaItem | UpdatePersonaItem,
    is_create: bool,
) -> list[PersonaFieldError]:
    """Resolve raw value fields to resource IDs (mutates item in place).

    For 'create' resources (name, description, instructions, examples):
      Creates a new resource via the create tool.
    For 'match' resources (color, icon, departments, voices, flags, parameter_fields):
      Searches by name via the search tool, matches exact (case-insensitive).

    Sequential tool calls — each acquires its own connection.
    Returns a list of errors (empty if all resolved).
    """
    from app.infra.persona.create import PersonaFieldError

    errors: list[PersonaFieldError] = []

    # --- Create resources ---

    if item.name is not None and item.name_id is None:
        async with pool.acquire() as conn:
            result = await create_name(conn, item.name, redis)
        item.name_id = result.id

    if item.description is not None and item.description_id is None:
        async with pool.acquire() as conn:
            result = await create_description(conn, item.description, redis)
        item.description_id = result.id

    if item.instructions is not None and item.instructions_id is None:
        async with pool.acquire() as conn:
            result = await create_instruction(conn, item.instructions, redis)
        item.instructions_id = result.id

    if item.examples is not None and item.example_ids is None:
        resolved_ids = []
        for ex in item.examples:
            async with pool.acquire() as conn:
                result = await create_example(conn, ex, redis)
            resolved_ids.append(result.id)
        item.example_ids = resolved_ids

    # --- Match resources ---

    if item.color is not None and item.color_id is None:
        async with pool.acquire() as conn:
            results = await search_colors(
                conn, redis, search=item.color, limit_count=20
            )
        match = next(
            (r for r in results if r.name and r.name.lower() == item.color.lower()),
            None,
        )
        if match and match.id:
            item.color_id = match.id
        else:
            errors.append(
                PersonaFieldError(
                    field="color", message=f'Color "{item.color}" not found'
                )
            )

    if item.icon is not None and item.icon_id is None:
        async with pool.acquire() as conn:
            results = await search_icons(conn, redis, search=item.icon, limit_count=20)
        match = next(
            (r for r in results if r.name and r.name.lower() == item.icon.lower()),
            None,
        )
        if match and match.id:
            item.icon_id = match.id
        else:
            errors.append(
                PersonaFieldError(field="icon", message=f'Icon "{item.icon}" not found')
            )

    if item.active_flag is not None and item.active_flag_id is None:
        async with pool.acquire() as conn:
            results = await search_flags(
                conn,
                redis,
                search=None,
                flag_type="persona_active",
                limit_count=100,
            )
        match = next((r for r in results if r.type == "persona_active"), None)
        if match and match.id:
            if item.active_flag:
                item.active_flag_id = match.id
        elif item.active_flag:
            errors.append(
                PersonaFieldError(
                    field="active_flag", message="Active flag resource not found"
                )
            )

    if item.departments is not None and item.department_ids is None:
        async with pool.acquire() as conn:
            all_depts = await search_departments(
                conn, redis, search=None, limit_count=1000
            )
        dept_name_map = {d.name.lower(): d.id for d in all_depts if d.name and d.id}
        resolved_ids = []
        for dept_name in item.departments:
            dept_id = dept_name_map.get(dept_name.lower())
            if dept_id:
                resolved_ids.append(dept_id)
            else:
                errors.append(
                    PersonaFieldError(
                        field="departments",
                        message=f'Department "{dept_name}" not found',
                    )
                )
        if not any(e.field == "departments" for e in errors):
            item.department_ids = resolved_ids

    if item.voices is not None and item.voice_ids is None:
        async with pool.acquire() as conn:
            all_voices = await search_voices(
                conn,
                redis,
                search=None,
                limit_count=1000,
            )
        voice_name_map = {v.voice.lower(): v.id for v in all_voices if v.voice and v.id}
        resolved_ids = []
        for voice_name in item.voices:
            vid = voice_name_map.get(voice_name.lower())
            if vid:
                resolved_ids.append(vid)
            else:
                errors.append(
                    PersonaFieldError(
                        field="voices",
                        message=f'Voice "{voice_name}" not found',
                    )
                )
        if not any(e.field == "voices" for e in errors):
            item.voice_ids = resolved_ids

    if item.parameter_fields is not None and item.parameter_field_ids is None:
        async with pool.acquire() as conn:
            all_pf = await search_parameter_fields(conn, redis)
        field_ids_list = [pf.field_id for pf in all_pf if pf.field_id]
        if field_ids_list:
            async with pool.acquire() as conn:
                fields_list = await get_fields(conn, field_ids_list, redis)
        else:
            fields_list = []
        field_name_map = {f.id: f.name for f in fields_list if f.name}
        pf_name_map = {
            field_name_map[pf.field_id].lower(): pf.id
            for pf in all_pf
            if pf.field_id and pf.id and pf.field_id in field_name_map
        }
        resolved_ids = []
        for pf_name in item.parameter_fields:
            pf_id = pf_name_map.get(pf_name.lower())
            if pf_id:
                resolved_ids.append(pf_id)
            else:
                errors.append(
                    PersonaFieldError(
                        field="parameter_fields",
                        message=f'Parameter field "{pf_name}" not found',
                    )
                )
        if not any(e.field == "parameter_fields" for e in errors):
            item.parameter_field_ids = resolved_ids

    # --- Validate required fields (create only) ---

    if is_create:
        if item.name_id is None:
            errors.append(PersonaFieldError(field="name", message="Name is required"))
        if item.color_id is None and item.color is None:
            errors.append(PersonaFieldError(field="color", message="Color is required"))
        if item.icon_id is None and item.icon is None:
            errors.append(PersonaFieldError(field="icon", message="Icon is required"))
        if item.instructions_id is None and item.instructions is None:
            errors.append(
                PersonaFieldError(
                    field="instructions", message="Instructions is required"
                )
            )

    return errors


async def create_denormalized_snapshot(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    id: UUID | None = None,
    name_id: UUID | None,
    description_id: UUID | None,
    color_id: UUID | None,
    icon_id: UUID | None,
    instructions_id: UUID | None,
    department_ids: list[UUID] | None,
    example_ids: list[UUID] | None,
    parameter_field_ids: list[UUID] | None,
) -> UUID:
    """Create a personas_resource snapshot by hydrating IDs to values.

    Read-only hydration uses pool (parallel), then the write uses a single conn.
    """

    # Parallel read-only hydration — each branch acquires its own connection.

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

    async def _get_colors() -> list:
        if not color_id:
            return []
        async with pool.acquire() as conn:
            return await get_colors(conn, [color_id], redis, bypass_cache=True)

    async def _get_icons() -> list:
        if not icon_id:
            return []
        async with pool.acquire() as conn:
            return await get_icons(conn, [icon_id], redis, bypass_cache=True)

    async def _get_instructions() -> list:
        if not instructions_id:
            return []
        async with pool.acquire() as conn:
            return await get_instructions(
                conn, [instructions_id], redis, bypass_cache=True
            )

    async def _get_examples() -> list:
        if not example_ids:
            return []
        async with pool.acquire() as conn:
            return await get_examples(conn, example_ids, redis, bypass_cache=True)

    (
        names,
        descriptions,
        colors,
        icons,
        instructions,
        examples_list,
    ) = await asyncio.gather(
        _get_names(),
        _get_descriptions(),
        _get_colors(),
        _get_icons(),
        _get_instructions(),
        _get_examples(),
    )

    # Write — single connection
    async with pool.acquire() as conn:
        result = await create_persona_resource(
            conn,
            redis,
            id=id,
            name=names[0].name if names else "",
            description=descriptions[0].description if descriptions else "",
            icon=icons[0].value if icons else "",
            color=colors[0].hex_code if colors else "",
            department_ids=department_ids,
            instructions=instructions[0].template if instructions else "",
            examples=[e.example for e in examples_list],
            parameter_field_ids=parameter_field_ids,
        )
    return result.id
