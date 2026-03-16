"""Resolve scenario artifact context — merged junctions + hydrated resources.

Given a scenario_id (and optional draft_id), fetches the published artifact
and draft entry, merges junction IDs (draft overrides published), then
hydrates all resources in parallel (selected + suggestions).

Composes existing black-box fetchers — no raw SQL (except document upload resolution).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.types import ArtifactContext, ResourcePair

# Artifact + draft fetchers
from app.tools.artifacts.scenario.get import (
    get_scenarios as get_scenario_artifacts,
)

# Entry MV fetchers (aliased to avoid collision with resource search functions)
from app.tools.entries.files.search import search_files as search_file_entries
from app.tools.entries.images.search import (
    search_images as search_image_entries,
)
from app.tools.entries.scenario_drafts.get import get_scenario_drafts
from app.tools.entries.videos.search import (
    search_videos as search_video_entries,
)

# Resource get fetchers (by known IDs)
from app.tools.resources.departments.get import get_departments

# Resource search fetchers (bounded, paginated)
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.documents.get import get_documents
from app.tools.resources.documents.search import search_documents
from app.tools.resources.fields.search import search_fields
from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.search import search_flags
from app.tools.resources.images.get import get_images
from app.tools.resources.images.search import search_images
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names
from app.tools.resources.objectives.get import get_objectives
from app.tools.resources.options.get import get_options
from app.tools.resources.options.search import search_options
from app.tools.resources.parameter_fields.get import get_parameter_fields
from app.tools.resources.parameter_fields.search import (
    search_parameter_fields,
)
from app.tools.resources.parameters.get import get_parameters
from app.tools.resources.parameters.search import search_parameters
from app.tools.resources.personas.get import get_personas
from app.tools.resources.personas.search import search_personas
from app.tools.resources.problem_statements.get import get_problem_statements
from app.tools.resources.problem_statements.search import (
    search_problem_statements,
)
from app.tools.resources.questions.get import get_questions
from app.tools.resources.questions.search import search_questions
from app.tools.resources.videos.get import get_videos
from app.tools.resources.videos.search import search_videos

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

SCENARIO_FLAG_TYPES = {
    "scenario_active",
    "video_enabled",
    "problem_statement_enabled",
    "objectives_enabled",
    "images_enabled",
    "questions_enabled",
}


# ---------------------------------------------------------------------------
# resolve_scenario_context
# ---------------------------------------------------------------------------


async def resolve_scenario_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    scenario_id: UUID | None,
    group_id: UUID,
    draft_id: UUID | None = None,
    user_department_ids: list[UUID] | None = None,
    parameter_ids: list[UUID] | None = None,
    # Search filters
    description_search: str | None = None,
    persona_search: str | None = None,
    document_search: str | None = None,
    parameter_search: str | None = None,
    problem_statement_search: str | None = None,
    image_search: str | None = None,
    video_search: str | None = None,
    question_search: str | None = None,
    option_search: str | None = None,
    # Show-selected toggles
    persona_show_selected: bool | None = None,
    document_show_selected: bool | None = None,
    parameter_show_selected: bool | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve a scenario artifact into fully hydrated resources.

    Steps:
      1. Fetch artifact + draft in parallel → merge IDs
      2. Parallel hydrate: get (selected) + search (suggestions) per resource
      3. Upload enrichment for documents, images, videos
      4. Assemble ArtifactContext with ResourcePairs

    Each parallel branch acquires its own connection from the pool.
    """
    user_dept_ids = user_department_ids or []
    param_ids = parameter_ids or []

    # Step 1: fetch artifact + draft in parallel

    async def _fetch_artifact() -> list:
        if not scenario_id:
            return []
        async with pool.acquire() as conn:
            return await get_scenario_artifacts(
                conn,
                [scenario_id],
                active=None,
                names=True,
                descriptions=True,
                departments=True,
                flags=True,
                documents=True,
                images=True,
                objectives=True,
                options=True,
                parameter_fields=True,
                personas=True,
                problem_statements=True,
                questions=True,
                videos=True,
            )

    async def _fetch_draft() -> list:
        if not draft_id:
            return []
        async with pool.acquire() as conn:
            return await get_scenario_drafts(conn, [draft_id])

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
                scenario=True,
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
                search=description_search,
                draft_id=group_id,
                exclude_ids=merged.description_ids,
                bypass_cache=bypass_cache,
                scenario=True,
            )

    async def _get_problem_statements() -> list:
        async with pool.acquire() as conn:
            return await get_problem_statements(
                conn, merged.problem_statement_ids, redis, bypass_cache
            )

    async def _search_problem_statements() -> list:
        async with pool.acquire() as conn:
            return await search_problem_statements(
                conn,
                redis,
                search=problem_statement_search,
                limit_count=20,
                offset_count=0,
                exclude_ids=merged.problem_statement_ids,
                bypass_cache=bypass_cache,
                scenario=True,
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
                scenario=True,
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
                suggest_source="all" if scenario_id is None else "recent",
                exclude_ids=merged.department_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_personas() -> list:
        async with pool.acquire() as conn:
            return await get_personas(conn, merged.persona_ids, redis, bypass_cache)

    async def _search_personas() -> list:
        async with pool.acquire() as conn:
            return await search_personas(
                conn,
                redis,
                search=persona_search,
                limit_count=20,
                offset_count=0,
                department_ids=user_dept_ids,
                draft_id=group_id,
                suggest_source="selected" if persona_show_selected else None,
                exclude_ids=merged.persona_ids,
                bypass_cache=bypass_cache,
                scenario=True,
            )

    async def _get_documents() -> list:
        async with pool.acquire() as conn:
            return await get_documents(conn, merged.document_ids, redis, bypass_cache)

    async def _search_documents() -> list:
        async with pool.acquire() as conn:
            return await search_documents(
                conn,
                redis,
                search=document_search,
                limit_count=20,
                offset_count=0,
                department_ids=user_dept_ids,
                draft_id=group_id,
                suggest_source="selected" if document_show_selected else None,
                exclude_ids=merged.document_ids,
                bypass_cache=bypass_cache,
                scenario=True,
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
                search=parameter_search,
                limit_count=20,
                offset_count=0,
                persona_parameter=None,
                document_parameter=None,
                scenario_parameter=True,
                video_parameter=None,
                suggest_source="selected" if parameter_show_selected else "all",
                exclude_ids=param_ids,
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

    async def _get_objectives() -> list:
        async with pool.acquire() as conn:
            return await get_objectives(conn, merged.objective_ids, redis, bypass_cache)

    async def _get_images() -> list:
        async with pool.acquire() as conn:
            return await get_images(conn, merged.image_ids, redis, bypass_cache)

    async def _search_images() -> list:
        async with pool.acquire() as conn:
            return await search_images(
                conn,
                redis,
                search=image_search,
                limit_count=20,
                offset_count=0,
                exclude_ids=merged.image_ids,
                bypass_cache=bypass_cache,
                scenario=True,
            )

    async def _get_videos() -> list:
        async with pool.acquire() as conn:
            return await get_videos(conn, merged.video_ids, redis, bypass_cache)

    async def _search_videos() -> list:
        async with pool.acquire() as conn:
            return await search_videos(
                conn,
                redis,
                search=video_search,
                limit_count=20,
                offset_count=0,
                exclude_ids=merged.video_ids,
                bypass_cache=bypass_cache,
                scenario=True,
            )

    async def _get_questions() -> list:
        async with pool.acquire() as conn:
            return await get_questions(conn, merged.question_ids, redis, bypass_cache)

    async def _search_questions() -> list:
        async with pool.acquire() as conn:
            return await search_questions(
                conn,
                redis,
                search=question_search,
                limit_count=20,
                offset_count=0,
                exclude_ids=merged.question_ids,
                bypass_cache=bypass_cache,
                scenario=True,
            )

    async def _get_options() -> list:
        async with pool.acquire() as conn:
            return await get_options(conn, merged.option_ids, redis, bypass_cache)

    async def _search_options() -> list:
        async with pool.acquire() as conn:
            return await search_options(
                conn,
                redis,
                search=option_search,
                limit_count=20,
                offset_count=0,
                exclude_ids=merged.option_ids,
                question_ids=merged.question_ids or None,
                bypass_cache=bypass_cache,
                scenario=True,
            )

    async def _search_fields_catalog() -> list:
        async with pool.acquire() as conn:
            return await search_fields(
                conn,
                redis,
                search=None,
                limit_count=200,
                offset_count=0,
                bypass_cache=bypass_cache,
            )

    (
        names_selected,
        names_suggestions,
        descriptions_selected,
        descriptions_suggestions,
        problem_statements_selected,
        problem_statements_suggestions,
        flags_selected,
        flags_suggestions,
        departments_selected,
        departments_suggestions,
        personas_selected,
        personas_suggestions,
        documents_selected,
        documents_suggestions,
        parameters_selected,
        parameters_suggestions,
        parameter_fields_selected,
        parameter_fields_suggestions,
        objectives_selected,
        images_selected,
        images_suggestions,
        videos_selected,
        videos_suggestions,
        questions_selected,
        questions_suggestions,
        options_selected,
        options_suggestions,
        fields_catalog,
    ) = await asyncio.gather(
        _get_names(),
        _search_names(),
        _get_descriptions(),
        _search_descriptions(),
        _get_problem_statements(),
        _search_problem_statements(),
        _get_flags(),
        _search_flags(),
        _get_departments(),
        _search_departments(),
        _get_personas(),
        _search_personas(),
        _get_documents(),
        _search_documents(),
        _get_parameters(),
        _search_parameters(),
        _get_parameter_fields(),
        _search_parameter_fields(),
        _get_objectives(),
        _get_images(),
        _search_images(),
        _get_videos(),
        _search_videos(),
        _get_questions(),
        _search_questions(),
        _get_options(),
        _search_options(),
        _search_fields_catalog(),
    )

    # Filter flags to scenario-specific types
    flags_suggestions_filtered = [
        f for f in flags_suggestions if getattr(f, "type", None) in SCENARIO_FLAG_TYPES
    ]

    # Step 3: Entry MV fetches (files, images, videos — for file_path/mime_type)
    all_doc_file_ids = [
        d.file_id for d in documents_selected + documents_suggestions if d.file_id
    ]
    all_image_ids = [i.id for i in images_selected + images_suggestions if i.id]
    all_video_ids = [v.id for v in videos_selected + videos_suggestions if v.id]

    async def _fetch_file_entries() -> list:
        if not all_doc_file_ids:
            return []
        async with pool.acquire() as conn:
            return await search_file_entries(
                conn, files_ids=all_doc_file_ids, limit=200
            )

    async def _fetch_image_entries() -> list:
        if not all_image_ids:
            return []
        async with pool.acquire() as conn:
            return await search_image_entries(conn, images_ids=all_image_ids, limit=200)

    async def _fetch_video_entries() -> list:
        if not all_video_ids:
            return []
        async with pool.acquire() as conn:
            return await search_video_entries(conn, videos_ids=all_video_ids, limit=200)

    file_entries, image_entries, video_entries = await asyncio.gather(
        _fetch_file_entries(),
        _fetch_image_entries(),
        _fetch_video_entries(),
    )

    return ArtifactContext(
        artifact_id=artifact.id if artifact else None,
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
            "problem_statements": ResourcePair(
                selected=problem_statements_selected,
                suggestions=problem_statements_suggestions,
            ),
            "flags": ResourcePair(
                selected=flags_selected, suggestions=flags_suggestions_filtered
            ),
            "departments": ResourcePair(
                selected=departments_selected, suggestions=departments_suggestions
            ),
            "personas": ResourcePair(
                selected=personas_selected, suggestions=personas_suggestions
            ),
            "documents": ResourcePair(
                selected=documents_selected, suggestions=documents_suggestions
            ),
            "parameters": ResourcePair(
                selected=parameters_selected, suggestions=parameters_suggestions
            ),
            "parameter_fields": ResourcePair(
                selected=parameter_fields_selected,
                suggestions=parameter_fields_suggestions,
            ),
            "objectives": ResourcePair(selected=objectives_selected, suggestions=[]),
            "images": ResourcePair(
                selected=images_selected, suggestions=images_suggestions
            ),
            "videos": ResourcePair(
                selected=videos_selected, suggestions=videos_suggestions
            ),
            "questions": ResourcePair(
                selected=questions_selected, suggestions=questions_suggestions
            ),
            "options": ResourcePair(
                selected=options_selected, suggestions=options_suggestions
            ),
            "fields": ResourcePair(selected=[], suggestions=fields_catalog),
        },
        entries={
            "files": file_entries,
            "images": image_entries,
            "videos": video_entries,
        },
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


@dataclass
class _MergedIds:
    """Merged junction IDs from artifact + draft."""

    name_ids: list[UUID]
    description_ids: list[UUID]
    problem_statement_ids: list[UUID]
    flag_ids: list[UUID]
    department_ids: list[UUID]
    persona_ids: list[UUID]
    document_ids: list[UUID]
    parameter_field_ids: list[UUID]
    objective_ids: list[UUID]
    image_ids: list[UUID]
    video_ids: list[UUID]
    question_ids: list[UUID]
    option_ids: list[UUID]


def _merge_junction_ids(artifact, draft) -> _MergedIds:
    """Merge artifact junction IDs with draft overrides.

    For all resources: draft overrides the entire list if it has any IDs.
    """
    name_ids = list(artifact.name_ids or []) if artifact else []
    description_ids = list(artifact.description_ids or []) if artifact else []
    problem_statement_ids = (
        list(artifact.problem_statement_ids or []) if artifact else []
    )
    flag_ids = list(artifact.flag_ids or []) if artifact else []
    department_ids = list(artifact.department_ids or []) if artifact else []
    persona_ids = list(artifact.persona_ids or []) if artifact else []
    document_ids = list(artifact.document_ids or []) if artifact else []
    parameter_field_ids = list(artifact.parameter_field_ids or []) if artifact else []
    objective_ids = list(artifact.objective_ids or []) if artifact else []
    image_ids = list(artifact.image_ids or []) if artifact else []
    video_ids = list(artifact.video_ids or []) if artifact else []
    question_ids = list(artifact.question_ids or []) if artifact else []
    option_ids = list(artifact.option_ids or []) if artifact else []

    # Draft overrides (if present)
    if draft:
        if draft.name_ids:
            name_ids = list(draft.name_ids)
        if draft.description_ids:
            description_ids = list(draft.description_ids)
        if draft.problem_statement_ids:
            problem_statement_ids = list(draft.problem_statement_ids)
        if draft.flag_ids:
            flag_ids = list(draft.flag_ids)
        if draft.department_ids:
            department_ids = list(draft.department_ids)
        if draft.persona_ids:
            persona_ids = list(draft.persona_ids)
        if draft.document_ids:
            document_ids = list(draft.document_ids)
        if draft.parameter_field_ids:
            parameter_field_ids = list(draft.parameter_field_ids)
        if draft.objective_ids:
            objective_ids = list(draft.objective_ids)
        if draft.image_ids:
            image_ids = list(draft.image_ids)
        if draft.video_ids:
            video_ids = list(draft.video_ids)
        if draft.question_ids:
            question_ids = list(draft.question_ids)
        if draft.option_ids:
            option_ids = list(draft.option_ids)

    return _MergedIds(
        name_ids=name_ids,
        description_ids=description_ids,
        problem_statement_ids=problem_statement_ids,
        flag_ids=flag_ids,
        department_ids=department_ids,
        persona_ids=persona_ids,
        document_ids=document_ids,
        parameter_field_ids=parameter_field_ids,
        objective_ids=objective_ids,
        image_ids=image_ids,
        video_ids=video_ids,
        question_ids=question_ids,
        option_ids=option_ids,
    )
