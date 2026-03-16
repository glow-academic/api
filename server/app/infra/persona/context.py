"""Resolve persona artifact context — merged junctions + hydrated resources.

Given a persona_id (and optional draft_id), fetches the published artifact
and draft entry, merges junction IDs (draft overrides published), then
hydrates all resources in parallel (selected + suggestions).

Each parallel branch acquires its own connection from the pool.
Composes existing black-box fetchers — no raw SQL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.types import ArtifactContext, ResourcePair

# Artifact + draft fetchers
from app.tools.artifacts.persona.get import (
    get_personas as get_persona_artifacts,
)
from app.tools.entries.persona_drafts.get import get_persona_drafts

# Resource get fetchers (by known IDs)
from app.tools.resources.colors.get import get_colors

# Resource search fetchers (bounded, paginated)
from app.tools.resources.colors.search import search_colors
from app.tools.resources.departments.get import get_departments
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.examples.get import get_examples
from app.tools.resources.examples.search import search_examples
from app.tools.resources.fields.search import search_fields
from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.search import search_flags
from app.tools.resources.icons.get import get_icons
from app.tools.resources.icons.search import search_icons
from app.tools.resources.instructions.get import get_instructions
from app.tools.resources.instructions.search import search_instructions
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names
from app.tools.resources.parameter_fields.get import get_parameter_fields
from app.tools.resources.parameter_fields.search import (
    search_parameter_fields,
)
from app.tools.resources.parameters.get import get_parameters
from app.tools.resources.parameters.search import search_parameters
from app.tools.resources.voices.get import get_voices
from app.tools.resources.voices.search import search_voices

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

PERSONA_FLAG_TYPES = {"persona_active"}


# ---------------------------------------------------------------------------
# resolve_persona_context
# ---------------------------------------------------------------------------


async def resolve_persona_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    persona_id: UUID | None,
    group_id: UUID,
    draft_id: UUID | None = None,
    user_department_ids: list[UUID] | None = None,
    parameter_ids: list[UUID] | None = None,
    # Search filters
    color_search: str | None = None,
    icon_search: str | None = None,
    descriptions_search: str | None = None,
    instructions_search: str | None = None,
    # Show-selected toggles
    color_show_selected: bool | None = None,
    icon_show_selected: bool | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve a persona artifact into fully hydrated resources.

    Steps:
      1. Fetch artifact + draft in parallel → merge IDs
      2. Parallel hydrate: get (selected) + search (suggestions) per resource
      3. Assemble ArtifactContext with ResourcePairs

    Each parallel branch acquires its own connection from the pool.
    """
    user_dept_ids = user_department_ids or []
    param_ids = parameter_ids or []

    # Step 1: fetch artifact + draft in parallel

    async def _fetch_artifact() -> list:
        if not persona_id:
            return []
        async with pool.acquire() as conn:
            return await get_persona_artifacts(
                conn,
                [persona_id],
                active=None,
                names=True,
                descriptions=True,
                colors=True,
                departments=True,
                examples=True,
                flags=True,
                icons=True,
                instructions=True,
                parameter_fields=True,
                voices=True,
            )

    async def _fetch_draft() -> list:
        if not draft_id:
            return []
        async with pool.acquire() as conn:
            return await get_persona_drafts(conn, [draft_id])

    artifacts, drafts = await asyncio.gather(_fetch_artifact(), _fetch_draft())

    artifact = artifacts[0] if artifacts else None
    draft = drafts[0] if drafts else None

    # Merge IDs: start from published, draft overrides if present
    merged = _merge_junction_ids(artifact, draft)
    draft_version = draft.version if draft else None
    active = artifact.active if artifact else True

    # Step 2: parallel hydrate — selected + suggestions for each resource
    # Each branch acquires its own connection from the pool.

    async def _get_names() -> list:
        async with pool.acquire() as conn:
            return await get_names(conn, merged.name_ids, redis, bypass_cache)

    async def _search_names() -> list:
        async with pool.acquire() as conn:
            return await search_names(
                conn,
                redis,
                draft_id=group_id,
                exclude_ids=merged.name_ids,
                bypass_cache=bypass_cache,
                persona=True,
            )

    async def _get_descriptions() -> list:
        async with pool.acquire() as conn:
            return await get_descriptions(
                conn, merged.description_ids, redis, bypass_cache
            )

    async def _search_descriptions() -> list:
        async with pool.acquire() as conn:
            return await search_descriptions(
                conn,
                redis,
                search=descriptions_search,
                draft_id=group_id,
                suggest_source="all",
                exclude_ids=merged.description_ids,
                bypass_cache=bypass_cache,
                persona=True,
            )

    async def _get_colors() -> list:
        async with pool.acquire() as conn:
            return await get_colors(conn, merged.color_ids, redis, bypass_cache)

    async def _search_colors() -> list:
        async with pool.acquire() as conn:
            return await search_colors(
                conn,
                redis,
                search=color_search,
                limit_count=20,
                offset_count=0,
                draft_id=group_id,
                suggest_source="selected" if color_show_selected else "all",
                exclude_ids=merged.color_ids,
                bypass_cache=bypass_cache,
                persona=True,
            )

    async def _get_icons() -> list:
        async with pool.acquire() as conn:
            return await get_icons(conn, merged.icon_ids, redis, bypass_cache)

    async def _search_icons() -> list:
        async with pool.acquire() as conn:
            return await search_icons(
                conn,
                redis,
                search=icon_search,
                limit_count=20,
                offset_count=0,
                draft_id=group_id,
                suggest_source="selected" if icon_show_selected else "all",
                exclude_ids=merged.icon_ids,
                bypass_cache=bypass_cache,
                persona=True,
            )

    async def _get_instructions() -> list:
        async with pool.acquire() as conn:
            return await get_instructions(
                conn, merged.instruction_ids, redis, bypass_cache
            )

    async def _search_instructions() -> list:
        async with pool.acquire() as conn:
            return await search_instructions(
                conn,
                redis,
                search=instructions_search,
                limit_count=20,
                offset_count=0,
                draft_id=group_id,
                suggest_source="all",
                exclude_ids=merged.instruction_ids,
                bypass_cache=bypass_cache,
                persona=True,
            )

    async def _get_flags() -> list:
        async with pool.acquire() as conn:
            return await get_flags(conn, merged.flag_ids, redis, bypass_cache)

    async def _search_flags() -> list:
        async with pool.acquire() as conn:
            return await search_flags(
                conn,
                redis,
                search=None,
                limit_count=50,
                offset_count=0,
                exclude_ids=merged.flag_ids,
                bypass_cache=bypass_cache,
                persona=True,
            )

    async def _get_departments() -> list:
        async with pool.acquire() as conn:
            return await get_departments(
                conn, merged.department_ids, redis, bypass_cache
            )

    async def _search_departments() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                department_ids=user_dept_ids,
                suggest_source="all",
                exclude_ids=merged.department_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_parameter_fields() -> list:
        async with pool.acquire() as conn:
            return await get_parameter_fields(
                conn, merged.parameter_field_ids, redis, bypass_cache
            )

    async def _search_parameter_fields() -> list:
        if not param_ids:
            return []
        async with pool.acquire() as conn:
            return await search_parameter_fields(
                conn,
                redis,
                parameter_ids=param_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_examples() -> list:
        async with pool.acquire() as conn:
            return await get_examples(conn, merged.example_ids, redis, bypass_cache)

    async def _search_examples() -> list:
        async with pool.acquire() as conn:
            return await search_examples(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                persona_id=persona_id,
                department_ids=user_dept_ids,
                draft_id=group_id,
                suggest_source="all",
                exclude_ids=merged.example_ids,
                bypass_cache=bypass_cache,
                persona=True,
            )

    async def _get_voices() -> list:
        async with pool.acquire() as conn:
            return await get_voices(conn, merged.voice_ids, redis, bypass_cache)

    async def _search_voices() -> list:
        async with pool.acquire() as conn:
            return await search_voices(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=merged.voice_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_parameters() -> list:
        if not param_ids:
            return []
        async with pool.acquire() as conn:
            return await get_parameters(conn, param_ids, redis, bypass_cache)

    async def _search_parameters() -> list:
        async with pool.acquire() as conn:
            return await search_parameters(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                persona_parameter=True,
                document_parameter=None,
                scenario_parameter=None,
                video_parameter=None,
                suggest_source="all",
                exclude_ids=param_ids,
                bypass_cache=bypass_cache,
                persona=False,
            )

    async def _search_fields() -> list:
        async with pool.acquire() as conn:
            return await search_fields(
                conn,
                redis,
                search=None,
                limit_count=200,
                offset_count=0,
                department_ids=user_dept_ids,
                bypass_cache=bypass_cache,
            )

    (
        names_selected,
        names_suggestions,
        descriptions_selected,
        descriptions_suggestions,
        colors_selected,
        colors_suggestions,
        icons_selected,
        icons_suggestions,
        instructions_selected,
        instructions_suggestions,
        flags_selected,
        flags_suggestions,
        departments_selected,
        departments_suggestions,
        parameter_fields_selected,
        parameter_fields_suggestions,
        examples_selected,
        examples_suggestions,
        voices_selected,
        voices_suggestions,
        parameters_selected,
        parameters_suggestions,
        fields_catalog,
    ) = await asyncio.gather(
        _get_names(),
        _search_names(),
        _get_descriptions(),
        _search_descriptions(),
        _get_colors(),
        _search_colors(),
        _get_icons(),
        _search_icons(),
        _get_instructions(),
        _search_instructions(),
        _get_flags(),
        _search_flags(),
        _get_departments(),
        _search_departments(),
        _get_parameter_fields(),
        _search_parameter_fields(),
        _get_examples(),
        _search_examples(),
        _get_voices(),
        _search_voices(),
        _get_parameters(),
        _search_parameters(),
        _search_fields(),
    )

    # Filter flags to persona-specific types
    flags_suggestions_filtered = [
        f for f in flags_suggestions if getattr(f, "type", None) in PERSONA_FLAG_TYPES
    ]

    return ArtifactContext(
        artifact_id=persona_id,
        active=active,
        group_id=group_id,
        draft_version=draft_version,
        resources={
            "names": ResourcePair(
                selected=names_selected, suggestions=names_suggestions
            ),
            "descriptions": ResourcePair(
                selected=descriptions_selected, suggestions=descriptions_suggestions
            ),
            "colors": ResourcePair(
                selected=colors_selected, suggestions=colors_suggestions
            ),
            "icons": ResourcePair(
                selected=icons_selected, suggestions=icons_suggestions
            ),
            "instructions": ResourcePair(
                selected=instructions_selected, suggestions=instructions_suggestions
            ),
            "flags": ResourcePair(
                selected=flags_selected, suggestions=flags_suggestions_filtered
            ),
            "departments": ResourcePair(
                selected=departments_selected, suggestions=departments_suggestions
            ),
            "parameter_fields": ResourcePair(
                selected=parameter_fields_selected,
                suggestions=parameter_fields_suggestions,
            ),
            "examples": ResourcePair(
                selected=examples_selected, suggestions=examples_suggestions
            ),
            "voices": ResourcePair(
                selected=voices_selected, suggestions=voices_suggestions
            ),
            "parameters": ResourcePair(
                selected=parameters_selected, suggestions=parameters_suggestions
            ),
            "fields": ResourcePair(selected=[], suggestions=fields_catalog),
        },
        entries={},
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


@dataclass
class _MergedIds:
    """Merged junction IDs from artifact + draft."""

    name_ids: list[UUID]
    description_ids: list[UUID]
    color_ids: list[UUID]
    icon_ids: list[UUID]
    instruction_ids: list[UUID]
    flag_ids: list[UUID]
    department_ids: list[UUID]
    parameter_field_ids: list[UUID]
    example_ids: list[UUID]
    voice_ids: list[UUID]


def _merge_junction_ids(artifact, draft) -> _MergedIds:
    """Merge artifact junction IDs with draft overrides.

    For single-select resources (name, description, color, icon, instruction, flag):
      draft overrides if it has any IDs for that resource.
    For multi-select resources (departments, parameter_fields, examples, voices):
      draft overrides the entire list if it has any IDs for that resource.
    """
    # Start from artifact (published)
    name_ids = list(artifact.name_ids or []) if artifact else []
    description_ids = list(artifact.description_ids or []) if artifact else []
    color_ids = list(artifact.color_ids or []) if artifact else []
    icon_ids = list(artifact.icon_ids or []) if artifact else []
    instruction_ids = list(artifact.instruction_ids or []) if artifact else []
    flag_ids = list(artifact.flag_ids or []) if artifact else []
    department_ids = list(artifact.department_ids or []) if artifact else []
    parameter_field_ids = list(artifact.parameter_field_ids or []) if artifact else []
    example_ids = list(artifact.example_ids or []) if artifact else []
    voice_ids = list(artifact.voice_ids or []) if artifact else []

    # Draft overrides (if present)
    if draft:
        if draft.name_ids:
            name_ids = list(draft.name_ids)
        if draft.description_ids:
            description_ids = list(draft.description_ids)
        if draft.color_ids:
            color_ids = list(draft.color_ids)
        if draft.icon_ids:
            icon_ids = list(draft.icon_ids)
        if draft.instruction_ids:
            instruction_ids = list(draft.instruction_ids)
        if draft.flag_ids:
            flag_ids = list(draft.flag_ids)
        if draft.department_ids:
            department_ids = list(draft.department_ids)
        if draft.parameter_field_ids:
            parameter_field_ids = list(draft.parameter_field_ids)
        if draft.example_ids:
            example_ids = list(draft.example_ids)
        if draft.voice_ids:
            voice_ids = list(draft.voice_ids)

    return _MergedIds(
        name_ids=name_ids,
        description_ids=description_ids,
        color_ids=color_ids,
        icon_ids=icon_ids,
        instruction_ids=instruction_ids,
        flag_ids=flag_ids,
        department_ids=department_ids,
        parameter_field_ids=parameter_field_ids,
        example_ids=example_ids,
        voice_ids=voice_ids,
    )
