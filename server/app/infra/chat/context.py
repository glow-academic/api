"""Resolve chat artifact context — draft-only hydrated resources.

Chat is entry-based (no artifact table) and draft-only: if a draft exists,
use its IDs; otherwise all resource lists are empty.

Composes existing black-box fetchers — no raw SQL.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.types import ArtifactContext, ResourcePair

# Draft fetcher
from app.tools.entries.chat_drafts.get import get_chat_drafts

# Resource get fetchers (by known IDs)
from app.tools.resources.departments.get import get_departments

# Resource search fetchers (bounded, paginated)
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.documents.get import get_documents
from app.tools.resources.documents.search import search_documents
from app.tools.resources.fields.get import get_fields
from app.tools.resources.fields.search import search_fields
from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.search import search_flags
from app.tools.resources.images.get import get_images
from app.tools.resources.images.search import search_images
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names
from app.tools.resources.objectives.get import get_objectives
from app.tools.resources.objectives.search import search_objectives
from app.tools.resources.options.get import get_options
from app.tools.resources.options.search import search_options
from app.tools.resources.parameter_fields.get import get_parameter_fields
from app.tools.resources.parameter_fields.search import (
    search_parameter_fields,
)
from app.tools.resources.personas.get import get_personas
from app.tools.resources.personas.search import search_personas
from app.tools.resources.problem_statements.get import get_problem_statements
from app.tools.resources.problem_statements.search import (
    search_problem_statements,
)
from app.tools.resources.questions.get import get_questions
from app.tools.resources.questions.search import search_questions
from app.tools.resources.scenarios.get import get_scenarios
from app.tools.resources.scenarios.search import search_scenarios
from app.tools.resources.videos.get import get_videos
from app.tools.resources.videos.search import search_videos

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHAT_FLAG_NAMES = {"chat_active"}


# ---------------------------------------------------------------------------
# resolve_chat_context
# ---------------------------------------------------------------------------


async def resolve_chat_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    group_id: UUID,
    draft_id: UUID | None = None,
    user_department_ids: list[UUID] | None = None,
    # Search filters
    description_search: str | None = None,
    persona_search: str | None = None,
    document_search: str | None = None,
    problem_statement_search: str | None = None,
    image_search: str | None = None,
    video_search: str | None = None,
    question_search: str | None = None,
    option_search: str | None = None,
    # Show-selected toggles
    persona_show_selected: bool | None = None,
    document_show_selected: bool | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve a chat entry into fully hydrated resources for the GET endpoint.

    Draft-only pattern: if draft exists, use its IDs. If no draft, all ID
    lists are empty (no published fallback).

    Steps:
      1. Fetch draft (if draft_id provided)
      2. Extract IDs directly from draft (no merge)
      3. Parallel hydrate: get (selected) + search (suggestions) per resource
      4. Assemble ArtifactContext with ResourcePairs
    """
    user_dept_ids = user_department_ids or []

    # Step 1: fetch draft
    if draft_id:
        async with pool.acquire() as conn:
            drafts = await get_chat_drafts(conn, [draft_id])
    else:
        drafts = []
    draft = drafts[0] if drafts else None
    draft_version = draft.version if draft else None

    # Step 2: extract IDs directly from draft (draft-only — no merge)
    name_ids = list(draft.name_ids) if draft and draft.name_ids else []
    description_ids = (
        list(draft.description_ids) if draft and draft.description_ids else []
    )
    flag_ids = list(draft.flag_ids) if draft and draft.flag_ids else []
    department_ids = (
        list(draft.department_ids) if draft and draft.department_ids else []
    )
    persona_ids = list(draft.persona_ids) if draft and draft.persona_ids else []
    document_ids = list(draft.document_ids) if draft and draft.document_ids else []
    scenario_ids = list(draft.scenario_ids) if draft and draft.scenario_ids else []
    field_ids = list(draft.field_ids) if draft and draft.field_ids else []
    parameter_field_ids = (
        list(draft.parameter_field_ids) if draft and draft.parameter_field_ids else []
    )
    question_ids = list(draft.question_ids) if draft and draft.question_ids else []
    option_ids = list(draft.option_ids) if draft and draft.option_ids else []
    video_ids = list(draft.video_ids) if draft and draft.video_ids else []
    image_ids = list(draft.image_ids) if draft and draft.image_ids else []
    problem_statement_ids = (
        list(draft.problem_statement_ids)
        if draft and draft.problem_statement_ids
        else []
    )
    objective_ids = list(draft.objective_ids) if draft and draft.objective_ids else []

    # Step 3: parallel hydrate — selected + suggestions for each resource
    # Each call acquires its own connection from the pool for true parallelism.

    async def _get_names() -> list:
        async with pool.acquire() as c:
            return await get_names(c, name_ids, redis, bypass_cache)

    async def _search_names() -> list:
        async with pool.acquire() as c:
            return await search_names(
                c,
                redis,
                draft_id=group_id,
                exclude_ids=name_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_descriptions() -> list:
        async with pool.acquire() as c:
            return await get_descriptions(c, description_ids, redis, bypass_cache)

    async def _search_descriptions() -> list:
        async with pool.acquire() as c:
            return await search_descriptions(
                c,
                redis,
                search=description_search,
                draft_id=group_id,
                exclude_ids=description_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_flags() -> list:
        async with pool.acquire() as c:
            return await get_flags(c, flag_ids, redis, bypass_cache)

    async def _search_flags() -> list:
        async with pool.acquire() as c:
            return await search_flags(
                c,
                redis,
                search=None,
                limit_count=50,
                offset_count=0,
                exclude_ids=flag_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_departments() -> list:
        async with pool.acquire() as c:
            return await get_departments(c, department_ids, redis, bypass_cache)

    async def _search_departments() -> list:
        async with pool.acquire() as c:
            return await search_departments(
                c,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                department_ids=user_dept_ids,
                suggest_source="recent",
                exclude_ids=department_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_personas() -> list:
        async with pool.acquire() as c:
            return await get_personas(c, persona_ids, redis, bypass_cache)

    async def _search_personas() -> list:
        async with pool.acquire() as c:
            return await search_personas(
                c,
                redis,
                search=persona_search,
                limit_count=20,
                offset_count=0,
                department_ids=user_dept_ids,
                draft_id=group_id,
                suggest_source="selected" if persona_show_selected else None,
                exclude_ids=persona_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_documents() -> list:
        async with pool.acquire() as c:
            return await get_documents(c, document_ids, redis, bypass_cache)

    async def _search_documents() -> list:
        async with pool.acquire() as c:
            return await search_documents(
                c,
                redis,
                search=document_search,
                limit_count=20,
                offset_count=0,
                department_ids=user_dept_ids,
                draft_id=group_id,
                suggest_source="selected" if document_show_selected else None,
                exclude_ids=document_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_scenarios() -> list:
        async with pool.acquire() as c:
            return await get_scenarios(c, scenario_ids, redis, bypass_cache)

    async def _search_scenarios() -> list:
        async with pool.acquire() as c:
            return await search_scenarios(
                c,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=scenario_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_fields() -> list:
        async with pool.acquire() as c:
            return await get_fields(c, field_ids, redis, bypass_cache)

    async def _search_fields() -> list:
        async with pool.acquire() as c:
            return await search_fields(
                c,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=field_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_parameter_fields() -> list:
        async with pool.acquire() as c:
            return await get_parameter_fields(
                c, parameter_field_ids, redis, bypass_cache
            )

    async def _search_parameter_fields() -> list:
        async with pool.acquire() as c:
            return await search_parameter_fields(
                c,
                redis,
                limit_count=20,
                offset_count=0,
                exclude_ids=parameter_field_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_questions() -> list:
        async with pool.acquire() as c:
            return await get_questions(c, question_ids, redis, bypass_cache)

    async def _search_questions() -> list:
        async with pool.acquire() as c:
            return await search_questions(
                c,
                redis,
                search=question_search,
                limit_count=20,
                offset_count=0,
                exclude_ids=question_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_options() -> list:
        async with pool.acquire() as c:
            return await get_options(c, option_ids, redis, bypass_cache)

    async def _search_options() -> list:
        async with pool.acquire() as c:
            return await search_options(
                c,
                redis,
                search=option_search,
                limit_count=20,
                offset_count=0,
                exclude_ids=option_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_videos() -> list:
        async with pool.acquire() as c:
            return await get_videos(c, video_ids, redis, bypass_cache)

    async def _search_videos() -> list:
        async with pool.acquire() as c:
            return await search_videos(
                c,
                redis,
                search=video_search,
                limit_count=20,
                offset_count=0,
                exclude_ids=video_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_images() -> list:
        async with pool.acquire() as c:
            return await get_images(c, image_ids, redis, bypass_cache)

    async def _search_images() -> list:
        async with pool.acquire() as c:
            return await search_images(
                c,
                redis,
                search=image_search,
                limit_count=20,
                offset_count=0,
                exclude_ids=image_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_problem_statements() -> list:
        async with pool.acquire() as c:
            return await get_problem_statements(
                c, problem_statement_ids, redis, bypass_cache
            )

    async def _search_problem_statements() -> list:
        async with pool.acquire() as c:
            return await search_problem_statements(
                c,
                redis,
                search=problem_statement_search,
                limit_count=20,
                offset_count=0,
                exclude_ids=problem_statement_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_objectives() -> list:
        async with pool.acquire() as c:
            return await get_objectives(c, objective_ids, redis, bypass_cache)

    async def _search_objectives() -> list:
        async with pool.acquire() as c:
            return await search_objectives(
                c,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=objective_ids,
                bypass_cache=bypass_cache,
            )

    (
        names_selected,
        names_suggestions,
        descriptions_selected,
        descriptions_suggestions,
        flags_selected,
        flags_suggestions,
        departments_selected,
        departments_suggestions,
        personas_selected,
        personas_suggestions,
        documents_selected,
        documents_suggestions,
        scenarios_selected,
        scenarios_suggestions,
        fields_selected,
        fields_suggestions,
        parameter_fields_selected,
        parameter_fields_suggestions,
        questions_selected,
        questions_suggestions,
        options_selected,
        options_suggestions,
        videos_selected,
        videos_suggestions,
        images_selected,
        images_suggestions,
        problem_statements_selected,
        problem_statements_suggestions,
        objectives_selected,
        objectives_suggestions,
    ) = await asyncio.gather(
        _get_names(),
        _search_names(),
        _get_descriptions(),
        _search_descriptions(),
        _get_flags(),
        _search_flags(),
        _get_departments(),
        _search_departments(),
        _get_personas(),
        _search_personas(),
        _get_documents(),
        _search_documents(),
        _get_scenarios(),
        _search_scenarios(),
        _get_fields(),
        _search_fields(),
        _get_parameter_fields(),
        _search_parameter_fields(),
        _get_questions(),
        _search_questions(),
        _get_options(),
        _search_options(),
        _get_videos(),
        _search_videos(),
        _get_images(),
        _search_images(),
        _get_problem_statements(),
        _search_problem_statements(),
        _get_objectives(),
        _search_objectives(),
    )

    # Filter flags to chat-specific types
    flags_suggestions_filtered = [
        f for f in flags_suggestions if getattr(f, "name", None) in CHAT_FLAG_NAMES
    ]

    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=group_id,
        draft_version=draft_version,
        resources={
            "names": ResourcePair(
                selected=names_selected, suggestions=names_suggestions
            ),
            "descriptions": ResourcePair(
                selected=descriptions_selected, suggestions=descriptions_suggestions
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
            "scenarios": ResourcePair(
                selected=scenarios_selected, suggestions=scenarios_suggestions
            ),
            "fields": ResourcePair(
                selected=fields_selected, suggestions=fields_suggestions
            ),
            "parameter_fields": ResourcePair(
                selected=parameter_fields_selected,
                suggestions=parameter_fields_suggestions,
            ),
            "questions": ResourcePair(
                selected=questions_selected, suggestions=questions_suggestions
            ),
            "options": ResourcePair(
                selected=options_selected, suggestions=options_suggestions
            ),
            "videos": ResourcePair(
                selected=videos_selected, suggestions=videos_suggestions
            ),
            "images": ResourcePair(
                selected=images_selected, suggestions=images_suggestions
            ),
            "problem_statements": ResourcePair(
                selected=problem_statements_selected,
                suggestions=problem_statements_suggestions,
            ),
            "objectives": ResourcePair(
                selected=objectives_selected, suggestions=objectives_suggestions
            ),
        },
        entries={},
    )
