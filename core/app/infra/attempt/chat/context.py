"""Resolve chat artifact context — template-aware hydrated resources.

Chat is entry-based (no artifact table) and draft-only: if a draft exists,
use its IDs; otherwise all resource lists are empty.

When a chat_entry_id (template) is provided, constraints are derived internally:
  - Scenario flags gate which sections are enabled
  - Pre-set template IDs lock sections (selected only, no search)
  - Department is auto-resolved from user + template intersection
  - Scenarios and departments are never available for selection

Composes existing black-box fetchers — no raw SQL.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.flag_icons import hydrate_flag_icons
from app.infra.types import ArtifactContext, ResourcePair

# Template fetcher
from app.tools.entries.chat.get import get_chats

# Draft fetcher
from app.tools.entries.chat_drafts.get import get_chat_drafts

# Department resolution
from app.infra.attempt.department import resolve_attempt_department

# Profile type
from app.infra.profile_identity_context import ProfileIdentityContext

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
    chat_entry_id: UUID | None = None,
    draft_id: UUID | None = None,
    profile: ProfileIdentityContext | None = None,
    # Search filters
    names_search: str | None = None,
    description_search: str | None = None,
    flags_search: str | None = None,
    departments_search: str | None = None,
    persona_search: str | None = None,
    document_search: str | None = None,
    scenario_search: str | None = None,
    field_search: str | None = None,
    problem_statement_search: str | None = None,
    objective_search: str | None = None,
    image_search: str | None = None,
    video_search: str | None = None,
    question_search: str | None = None,
    option_search: str | None = None,
    # Limits
    names_limit: int | None = None,
    descriptions_limit: int | None = None,
    flags_limit: int | None = None,
    departments_limit: int | None = None,
    personas_limit: int | None = None,
    documents_limit: int | None = None,
    scenarios_limit: int | None = None,
    fields_limit: int | None = None,
    parameter_fields_limit: int | None = None,
    questions_limit: int | None = None,
    options_limit: int | None = None,
    videos_limit: int | None = None,
    images_limit: int | None = None,
    problem_statements_limit: int | None = None,
    objectives_limit: int | None = None,
    # Show-selected toggles
    persona_show_selected: bool | None = None,
    document_show_selected: bool | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve a chat entry into fully hydrated resources for the GET endpoint.

    All constraints are derived internally from the chat template
    (chat_entry_id) — no external flags needed.

    Steps:
      1. Fetch chat template (if chat_entry_id provided)
      2. Derive: enabled sections, locked sections, scoped department
      3. Fetch draft (if draft_id provided)
      4. Parallel hydrate: get (selected) + search (suggestions) per resource
      5. Assemble ArtifactContext with ResourcePairs (only enabled sections)
    """
    user_dept_ids = profile.department_ids if profile else []
    user_primary_dept_id = profile.primary_department_id if profile else None

    # ── Step 1: Fetch chat template ───────────────────────────────────────────
    template = None
    if chat_entry_id:
        async with pool.acquire() as conn:
            templates = await get_chats(conn, [chat_entry_id])
            template = templates[0] if templates else None

    # ── Step 2: Derive constraints from template ──────────────────────────────
    has_template = template is not None

    # Video mode vs chat mode — video_enabled is the master toggle
    is_video_mode = (template.video_enabled or False) if has_template else False

    # Determine which sections are enabled
    enabled: dict[str, bool] = {
        "names": True,                            # selectable
        "descriptions": True,                     # selectable
        "flags": not has_template,                # config flags — set by template
        "departments": not has_template,          # auto-resolved when template exists
        "personas": True,
        "documents": True,
        "scenarios": not has_template,            # from template, never selectable
        "fields": not has_template,               # context catalog — not relevant for attempt
        "parameter_fields": True,                 # selectable
        # Video mode: video → questions → options
        "videos": is_video_mode,
        "questions": is_video_mode,
        "options": is_video_mode,
        # Chat mode: images instead of video
        "images": (not is_video_mode) if has_template else True,
        # Independent flags
        "problem_statements": (template.problem_statement_enabled or False) if has_template else True,
        "objectives": (template.objectives_enabled or False) if has_template else True,
    }

    # Determine which sections are pre-satisfied (locked — template has IDs)
    locked: dict[str, bool] = {}
    if has_template:
        locked = {
            "names": bool(template.name_ids),
            "descriptions": bool(template.description_ids),
            "personas": bool(template.persona_ids),
            "documents": bool(template.document_ids),
            "questions": bool(template.question_ids),
            "options": bool(template.option_ids),
            "videos": bool(template.video_ids),
            "images": bool(template.image_ids),
            "problem_statements": bool(template.problem_statement_ids),
            "objectives": bool(template.objective_ids),
        }

    # Resolve department — intersect user + template departments
    scope_dept_ids = user_dept_ids
    if has_template and template.department_ids:
        dept_id = resolve_attempt_department(
            user_department_ids=user_dept_ids,
            user_primary_department_id=user_primary_dept_id,
            chat_department_ids=template.department_ids,
        )
        if dept_id:
            scope_dept_ids = [dept_id]

    # Resolve mode-scoped parameter_field_ids for persona/document filtering
    mode_pf_ids: list[UUID] | None = None
    if has_template:
        from app.infra.attempt.chat.mode import resolve_mode_parameter_field_ids
        async with pool.acquire() as conn:
            mode_pf_ids = await resolve_mode_parameter_field_ids(
                conn, redis,
                video_mode=is_video_mode,
                department_ids=scope_dept_ids,
            )

    # ── Step 3: Fetch draft ───────────────────────────────────────────────────
    if draft_id:
        async with pool.acquire() as conn:
            drafts = await get_chat_drafts(conn, [draft_id])
    else:
        drafts = []
    draft = drafts[0] if drafts else None

    # Merge draft over template defaults.
    name_ids = list(draft.name_ids) if draft and draft.name_ids else list(template.name_ids) if template and template.name_ids else []
    description_ids = list(draft.description_ids) if draft and draft.description_ids else list(template.description_ids) if template and template.description_ids else []
    flag_ids = list(draft.flag_ids) if draft and draft.flag_ids else list(template.flag_ids) if template and template.flag_ids else []
    department_ids = list(draft.department_ids) if draft and draft.department_ids else list(template.department_ids) if template and template.department_ids else []
    persona_ids = list(draft.persona_ids) if draft and draft.persona_ids else list(template.persona_ids) if template and template.persona_ids else []
    document_ids = list(draft.document_ids) if draft and draft.document_ids else list(template.document_ids) if template and template.document_ids else []
    scenario_ids = list(draft.scenario_ids) if draft and draft.scenario_ids else [template.scenario_id] if template and template.scenario_id else []
    field_ids = list(draft.field_ids) if draft and draft.field_ids else []
    parameter_field_ids = list(draft.parameter_field_ids) if draft and draft.parameter_field_ids else list(template.parameter_field_ids) if template and template.parameter_field_ids else []
    question_ids = list(draft.question_ids) if draft and draft.question_ids else list(template.question_ids) if template and template.question_ids else []
    option_ids = list(draft.option_ids) if draft and draft.option_ids else list(template.option_ids) if template and template.option_ids else []
    video_ids = list(draft.video_ids) if draft and draft.video_ids else list(template.video_ids) if template and template.video_ids else []
    image_ids = list(draft.image_ids) if draft and draft.image_ids else list(template.image_ids) if template and template.image_ids else []
    problem_statement_ids = list(draft.problem_statement_ids) if draft and draft.problem_statement_ids else list(template.problem_statement_ids) if template and template.problem_statement_ids else []
    objective_ids = list(draft.objective_ids) if draft and draft.objective_ids else list(template.objective_ids) if template and template.objective_ids else []

    pending_ids: set[UUID] = set()
    if draft:
        pending_ids |= set(getattr(draft, "pending_name_ids", []) or [])
        pending_ids |= set(getattr(draft, "pending_description_ids", []) or [])
        pending_ids |= set(getattr(draft, "pending_flag_ids", []) or [])
        pending_ids |= set(getattr(draft, "pending_department_ids", []) or [])
        pending_ids |= set(getattr(draft, "pending_persona_ids", []) or [])
        pending_ids |= set(getattr(draft, "pending_document_ids", []) or [])
        pending_ids |= set(getattr(draft, "pending_scenario_ids", []) or [])
        pending_ids |= set(getattr(draft, "pending_field_ids", []) or [])
        pending_ids |= set(getattr(draft, "pending_parameter_field_ids", []) or [])
        pending_ids |= set(getattr(draft, "pending_question_ids", []) or [])
        pending_ids |= set(getattr(draft, "pending_option_ids", []) or [])
        pending_ids |= set(getattr(draft, "pending_video_ids", []) or [])
        pending_ids |= set(getattr(draft, "pending_image_ids", []) or [])
        pending_ids |= set(getattr(draft, "pending_problem_statement_ids", []) or [])
        pending_ids |= set(getattr(draft, "pending_objective_ids", []) or [])

    # ── Step 4: Parallel hydrate ──────────────────────────────────────────────
    # Each closure acquires its own connection for true parallelism.
    # Sections that are disabled or locked short-circuit to empty lists.

    def _is_locked(key: str) -> bool:
        return locked.get(key, False)

    # --- Names ----------------------------------------------------------------

    async def _get_names() -> list:
        if not enabled["names"]:
            return []
        async with pool.acquire() as c:
            return await get_names(c, name_ids, redis, bypass_cache)

    async def _search_names() -> list:
        if not enabled["names"] or _is_locked("names"):
            return []
        async with pool.acquire() as c:
            return await search_names(
                c, redis,
                search=names_search,
                limit_count=names_limit or 20,
                draft_id=draft_id if has_template else group_id,
                suggest_source="draft" if has_template and draft_id else None,
                exclude_ids=name_ids, bypass_cache=bypass_cache,
            )

    # --- Descriptions ---------------------------------------------------------

    async def _get_descriptions() -> list:
        if not enabled["descriptions"]:
            return []
        async with pool.acquire() as c:
            return await get_descriptions(c, description_ids, redis, bypass_cache)

    async def _search_descriptions() -> list:
        if not enabled["descriptions"] or _is_locked("descriptions"):
            return []
        async with pool.acquire() as c:
            return await search_descriptions(
                c, redis, search=description_search,
                limit_count=descriptions_limit or 20,
                draft_id=draft_id if has_template else group_id,
                suggest_source="draft" if has_template and draft_id else None,
                exclude_ids=description_ids, bypass_cache=bypass_cache,
            )

    # --- Flags ----------------------------------------------------------------

    async def _get_flags() -> list:
        if not enabled["flags"]:
            return []
        async with pool.acquire() as c:
            return await get_flags(c, flag_ids, redis, bypass_cache)

    async def _search_flags() -> list:
        if not enabled["flags"] or _is_locked("flags"):
            return []
        async with pool.acquire() as c:
            return await search_flags(
                c, redis, search=flags_search, limit_count=flags_limit or 50, offset_count=0,
                exclude_ids=flag_ids, bypass_cache=bypass_cache,
            )

    # --- Departments ----------------------------------------------------------

    async def _get_departments() -> list:
        if not enabled["departments"]:
            return []
        async with pool.acquire() as c:
            return await get_departments(c, department_ids, redis, bypass_cache)

    async def _search_departments() -> list:
        if not enabled["departments"]:
            return []
        async with pool.acquire() as c:
            return await search_departments(
                c, redis, search=departments_search, limit_count=departments_limit or 20, offset_count=0,
                department_ids=user_dept_ids, suggest_source="recent",
                exclude_ids=department_ids, bypass_cache=bypass_cache,
            )

    # --- Personas -------------------------------------------------------------

    async def _get_personas() -> list:
        if not enabled["personas"]:
            return []
        async with pool.acquire() as c:
            return await get_personas(c, persona_ids, redis, bypass_cache)

    async def _search_personas() -> list:
        if not enabled["personas"] or _is_locked("personas"):
            return []
        async with pool.acquire() as c:
            return await search_personas(
                c, redis, search=persona_search, limit_count=personas_limit or 20, offset_count=0,
                department_ids=scope_dept_ids, draft_id=group_id,
                parameter_field_ids=mode_pf_ids,
                suggest_source="selected" if persona_show_selected else None,
                exclude_ids=persona_ids, bypass_cache=bypass_cache,
            )

    # --- Documents ------------------------------------------------------------

    async def _get_documents() -> list:
        if not enabled["documents"]:
            return []
        async with pool.acquire() as c:
            return await get_documents(c, document_ids, redis, bypass_cache)

    async def _search_documents() -> list:
        if not enabled["documents"] or _is_locked("documents"):
            return []
        async with pool.acquire() as c:
            return await search_documents(
                c, redis, search=document_search, limit_count=documents_limit or 20, offset_count=0,
                department_ids=scope_dept_ids, draft_id=group_id,
                parameter_field_ids=mode_pf_ids,
                suggest_source="selected" if document_show_selected else None,
                exclude_ids=document_ids, bypass_cache=bypass_cache,
            )

    # --- Scenarios ------------------------------------------------------------

    async def _get_scenarios() -> list:
        if not enabled["scenarios"]:
            return []
        async with pool.acquire() as c:
            return await get_scenarios(c, scenario_ids, redis, bypass_cache)

    async def _search_scenarios() -> list:
        if not enabled["scenarios"]:
            return []
        async with pool.acquire() as c:
            return await search_scenarios(
                c, redis, search=scenario_search, limit_count=scenarios_limit or 20, offset_count=0,
                exclude_ids=scenario_ids, bypass_cache=bypass_cache,
            )

    # --- Fields ---------------------------------------------------------------

    async def _get_fields() -> list:
        if not enabled["fields"]:
            return []
        async with pool.acquire() as c:
            return await get_fields(c, field_ids, redis, bypass_cache)

    async def _search_fields() -> list:
        if not enabled["fields"]:
            return []
        async with pool.acquire() as c:
            return await search_fields(
                c, redis, search=field_search, limit_count=fields_limit or 20, offset_count=0,
                exclude_ids=field_ids, bypass_cache=bypass_cache,
            )

    # --- Parameter Fields -----------------------------------------------------

    async def _get_parameter_fields() -> list:
        if not enabled["parameter_fields"]:
            return []
        async with pool.acquire() as c:
            return await get_parameter_fields(
                c, parameter_field_ids, redis, bypass_cache,
            )

    async def _search_parameter_fields() -> list:
        if not enabled["parameter_fields"]:
            return []
        # Scope to mode-appropriate parameter_field_ids if available
        pf_filter_ids = mode_pf_ids if mode_pf_ids else None
        async with pool.acquire() as c:
            if pf_filter_ids:
                # Only show parameter fields matching the mode
                from app.tools.resources.parameter_fields.get import get_parameter_fields as get_pfs
                # Filter mode_pf_ids to exclude already-selected
                available_ids = [pid for pid in pf_filter_ids if pid not in set(parameter_field_ids)]
                limited_ids = available_ids[: parameter_fields_limit or 20]
                return await get_pfs(c, limited_ids, redis, bypass_cache) if limited_ids else []
            return await search_parameter_fields(
                c, redis, limit_count=parameter_fields_limit or 20, offset_count=0,
                exclude_ids=parameter_field_ids, bypass_cache=bypass_cache,
            )

    # --- Questions ------------------------------------------------------------

    async def _get_questions() -> list:
        if not enabled["questions"]:
            return []
        async with pool.acquire() as c:
            return await get_questions(c, question_ids, redis, bypass_cache)

    async def _search_questions() -> list:
        if not enabled["questions"] or _is_locked("questions"):
            return []
        async with pool.acquire() as c:
            return await search_questions(
                c, redis, search=question_search, limit_count=questions_limit or 20, offset_count=0,
                exclude_ids=question_ids, bypass_cache=bypass_cache,
            )

    # --- Options --------------------------------------------------------------

    async def _get_options() -> list:
        if not enabled["options"]:
            return []
        async with pool.acquire() as c:
            return await get_options(c, option_ids, redis, bypass_cache)

    async def _search_options() -> list:
        if not enabled["options"] or _is_locked("options"):
            return []
        async with pool.acquire() as c:
            return await search_options(
                c, redis, search=option_search, limit_count=options_limit or 20, offset_count=0,
                exclude_ids=option_ids, bypass_cache=bypass_cache,
            )

    # --- Videos ---------------------------------------------------------------

    async def _get_videos() -> list:
        if not enabled["videos"]:
            return []
        async with pool.acquire() as c:
            return await get_videos(c, video_ids, redis, bypass_cache)

    async def _search_videos() -> list:
        if not enabled["videos"] or _is_locked("videos"):
            return []
        async with pool.acquire() as c:
            return await search_videos(
                c, redis, search=video_search, limit_count=videos_limit or 20, offset_count=0,
                exclude_ids=video_ids, bypass_cache=bypass_cache,
            )

    # --- Images ---------------------------------------------------------------

    async def _get_images() -> list:
        if not enabled["images"]:
            return []
        async with pool.acquire() as c:
            return await get_images(c, image_ids, redis, bypass_cache)

    async def _search_images() -> list:
        if not enabled["images"] or _is_locked("images"):
            return []
        async with pool.acquire() as c:
            return await search_images(
                c, redis, search=image_search, limit_count=images_limit or 20, offset_count=0,
                exclude_ids=image_ids, bypass_cache=bypass_cache,
            )

    # --- Problem Statements ---------------------------------------------------

    async def _get_problem_statements() -> list:
        if not enabled["problem_statements"]:
            return []
        async with pool.acquire() as c:
            return await get_problem_statements(
                c, problem_statement_ids, redis, bypass_cache,
            )

    async def _search_problem_statements() -> list:
        if not enabled["problem_statements"] or _is_locked("problem_statements"):
            return []
        async with pool.acquire() as c:
            return await search_problem_statements(
                c, redis, search=problem_statement_search, limit_count=problem_statements_limit or 20,
                offset_count=0, exclude_ids=problem_statement_ids,
                bypass_cache=bypass_cache,
            )

    # --- Objectives -----------------------------------------------------------

    async def _get_objectives() -> list:
        if not enabled["objectives"]:
            return []
        async with pool.acquire() as c:
            return await get_objectives(c, objective_ids, redis, bypass_cache)

    async def _search_objectives() -> list:
        if not enabled["objectives"] or _is_locked("objectives"):
            return []
        async with pool.acquire() as c:
            return await search_objectives(
                c, redis, search=objective_search, limit_count=objectives_limit or 20, offset_count=0,
                exclude_ids=objective_ids, bypass_cache=bypass_cache,
            )

    # ── Gather all in parallel ────────────────────────────────────────────────

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

    # Hydrate SVG icons onto each flag (icon_id → icon markup).
    async with pool.acquire() as conn:
        await hydrate_flag_icons(
            list(flags_selected) + list(flags_suggestions_filtered), conn, redis, bypass_cache
        )

    # Enrich parameter_fields with field name + parameter group name
    all_pf_items = list(parameter_fields_selected) + list(parameter_fields_suggestions)
    if all_pf_items:
        pf_field_ids = list({pf.field_id for pf in all_pf_items if pf.field_id})
        pf_param_ids = list({pf.parameter_id for pf in all_pf_items if pf.parameter_id})

        async def _enrich_fields() -> dict:
            if not pf_field_ids:
                return {}
            async with pool.acquire() as c:
                items = await get_fields(c, pf_field_ids, redis, bypass_cache)
            return {f.id: f for f in items}

        async def _enrich_params() -> dict:
            if not pf_param_ids:
                return {}
            from app.tools.resources.parameters.get import get_parameters
            async with pool.acquire() as c:
                items = await get_parameters(c, pf_param_ids, redis, bypass_cache)
            return {p.parameter_id: p for p in items}

        field_lookup, param_lookup = await asyncio.gather(
            _enrich_fields(), _enrich_params(),
        )
        for pf in all_pf_items:
            catalog_field = field_lookup.get(pf.field_id)
            if catalog_field:
                pf.name = catalog_field.name
            param = param_lookup.get(pf.parameter_id) if pf.parameter_id else None
            if param:
                pf.parameter_name = param.name

    # ── Step 5: Assemble — only include enabled sections ──────────────────────

    resources: dict[str, ResourcePair] = {}

    def _add(key: str, selected: list, suggestions: list) -> None:
        if enabled.get(key, True):
            resources[key] = ResourcePair(selected=selected, suggestions=suggestions)

    _add("names", names_selected, names_suggestions)
    _add("descriptions", descriptions_selected, descriptions_suggestions)
    _add("flags", flags_selected, flags_suggestions_filtered)
    _add("departments", departments_selected, departments_suggestions)
    _add("personas", personas_selected, personas_suggestions)
    _add("documents", documents_selected, documents_suggestions)
    _add("scenarios", scenarios_selected, scenarios_suggestions)
    _add("fields", fields_selected, fields_suggestions)
    _add("parameter_fields", parameter_fields_selected, parameter_fields_suggestions)
    _add("questions", questions_selected, questions_suggestions)
    _add("options", options_selected, options_suggestions)
    _add("videos", videos_selected, videos_suggestions)
    _add("images", images_selected, images_suggestions)
    _add("problem_statements", problem_statements_selected, problem_statements_suggestions)
    _add("objectives", objectives_selected, objectives_suggestions)

    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=group_id,
        resources=resources,
        entries={
            "pending_ids": pending_ids,
            "chat_exists": has_template or chat_entry_id is None,
        },
    )
