"""Attempt chat create logic — creates an attempt_chat from a chat template.

Called by:
  - POST /attempt/chat/create (HTTP)
  - The model as a tool call during /attempt/generate

Flow:
  1. Profile context + permission check
  2. Fetch chat template — derive config flags, rubrics, department
  3. Resolve values — lookup/create text resources, search complex resources
  4. Validate — flag gating, pre-satisfied locking, cardinality
  5. Merge — template pre-set + model selections + auto department
  6. Create run + call + attempt_chat + bridge in transaction
  7. Return { attempt_chat_id }
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.attempt_chat.create import create_attempt_chat
from app.tools.entries.attempt_chat.refresh import refresh_attempt_chat
from app.tools.entries.attempt_chat_bridge.create import create_attempt_chat_bridge
from app.tools.entries.attempt_chat_bridge.refresh import refresh_attempt_chat_bridge


# ---------------------------------------------------------------------------
# Value types for denormalized input
# ---------------------------------------------------------------------------


class AttemptOptionValue(BaseModel):
    """Inline option value — nested under a question."""

    option_text: str
    is_correct: bool = False


class AttemptQuestionValue(BaseModel):
    """Inline question value with optional nested options."""

    question_text: str
    allow_multiple: bool = False
    options: list[AttemptOptionValue] | None = None


# ---------------------------------------------------------------------------
# Request / Response
# ---------------------------------------------------------------------------


class CreateAttemptChatApiRequest(BaseModel):
    """Create an attempt_chat from a chat template + resource selections.

    Follows the persona pattern: singular fields enforce single-select,
    plural fields enforce multi-select. Each field supports either an ID
    (lookup by UUID) or a value (lookup by text / create if not found).

    Config flags, rubrics, standards, departments, and scenarios are all
    derived from the chat template — never passed by the model.
    """

    # Required context
    attempt_id: UUID
    chat_id: UUID

    # Single-select (ID or value — mutually exclusive)
    name_id: UUID | None = None
    name: str | None = None
    description_id: UUID | None = None
    description: str | None = None
    problem_statement_id: UUID | None = None
    problem_statement: str | None = None
    video_id: UUID | None = None              # ID only (upload-backed)
    image_id: UUID | None = None              # ID only (upload-backed)

    # Multi-select (IDs or values — mutually exclusive per pair)
    personas_ids: list[UUID] | None = None
    personas: list[str] | None = None         # search by name, error if not found
    documents_ids: list[UUID] | None = None
    documents: list[str] | None = None        # search by name, error if not found
    parameter_fields_ids: list[UUID] | None = None
    parameter_fields: list[str] | None = None  # search by field name, error if not found
    objectives_ids: list[UUID] | None = None
    objectives: list[str] | None = None       # search/create by text
    questions_ids: list[UUID] | None = None
    questions: list[AttemptQuestionValue] | None = None  # create with nested options
    options_ids: list[UUID] | None = None     # standalone existing options

    # Reuse previous attempt_chat instead of creating new
    previous_attempt_chat_id: UUID | None = None

    # Ack
    idempotency_key: UUID | None = None
    accept: bool = True


class CreateAttemptChatApiResponse(BaseModel):
    attempt_chat_id: UUID
    idempotency_key: UUID | None = None


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------


async def _resolve_single_text(
    conn: asyncpg.Connection,
    redis: Redis,
    *,
    resource_id: UUID | None,
    value: str | None,
    label: str,
    create_fn,
    create_kwarg: str,
) -> UUID | None:
    """Resolve a single-select text resource: ID wins, value creates."""
    if resource_id and value:
        raise HTTPException(400, f"Pass {label}_id or {label}, not both.")
    if resource_id:
        return resource_id
    if value:
        result = await create_fn(conn, **{create_kwarg: value}, redis=redis)
        return result.id
    return None


async def _resolve_multi_search(
    conn: asyncpg.Connection,
    redis: Redis,
    *,
    ids: list[UUID] | None,
    values: list[str] | None,
    label: str,
    search_fn,
    department_ids: list[UUID] | None = None,
) -> list[UUID] | None:
    """Resolve multi-select complex resources: IDs win, values search by name.

    Errors if any value cannot be found (never auto-creates).
    """
    if ids and values:
        raise HTTPException(400, f"Pass {label}_ids or {label}, not both.")
    if ids:
        return ids
    if not values:
        return None
    resolved: list[UUID] = []
    for v in values:
        results = await search_fn(
            conn, redis, search=v, limit_count=1,
            department_ids=department_ids, bypass_cache=True,
        )
        if not results:
            # Fetch available names for a helpful error message
            all_results = await search_fn(
                conn, redis, limit_count=20,
                department_ids=department_ids, bypass_cache=True,
            )
            available = [getattr(r, "name", None) or str(r.id) for r in all_results]
            hint = f"Available: {', '.join(available)}" if available else "No items available"
            raise HTTPException(400, f'{label} not found: "{v}". {hint}')
        resolved.append(results[0].id)
    return resolved


async def _resolve_multi_text(
    conn: asyncpg.Connection,
    redis: Redis,
    *,
    ids: list[UUID] | None,
    values: list[str] | None,
    label: str,
    create_fn,
    create_kwarg: str,
) -> list[UUID] | None:
    """Resolve multi-select text resources: IDs win, values create."""
    if ids and values:
        raise HTTPException(400, f"Pass {label}_ids or {label}, not both.")
    if ids:
        return ids
    if not values:
        return None
    resolved: list[UUID] = []
    for v in values:
        result = await create_fn(conn, **{create_kwarg: v}, redis=redis)
        resolved.append(result.id)
    return resolved


# ---------------------------------------------------------------------------
# Main impl
# ---------------------------------------------------------------------------


async def create_attempt_chat_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: CreateAttemptChatApiRequest,
    soft: bool = False,
    **_kwargs,
) -> CreateAttemptChatApiResponse:
    """Create an attempt_chat entry within an attempt.

    If previous_attempt_chat_id is provided, skips resource setup and just
    bridges the existing attempt_chat into the current attempt.
    """

    # ── Short-circuit: reuse previous attempt_chat ───────────────────────────

    if request.previous_attempt_chat_id:
        async with pool.acquire() as conn:
            await create_attempt_chat_bridge(
                conn,
                attempt_id=request.attempt_id,
                attempt_chat_id=request.previous_attempt_chat_id,
                session_id=session_id,
                soft=soft,
            )
        async with pool.acquire() as conn:
            await refresh_attempt_chat(conn)
            await refresh_attempt_chat_bridge(conn)
        return CreateAttemptChatApiResponse(
            attempt_chat_id=request.previous_attempt_chat_id,
            idempotency_key=request.idempotency_key,
        )

    # ── Step 1: Profile context + permissions ─────────────────────────────────

    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if profile is None:
        raise HTTPException(401, "Profile not found. Please sign in again.")

    if not has_permission(profile.role_permissions, "attempt", "start"):
        raise HTTPException(403, "You don't have permission to create attempt chats.")

    # ── Step 2: Fetch chat template ───────────────────────────────────────────

    from app.infra.attempt.department import resolve_attempt_department
    from app.tools.entries.chat.get import get_chat_entries_internal

    async with pool.acquire() as conn:
        templates = await get_chat_entries_internal(conn, [request.chat_id], bypass_cache=True)
    if not templates:
        raise HTTPException(404, "Chat template not found.")
    tmpl = templates[0]

    # Auto-resolve department
    department_id = resolve_attempt_department(
        user_department_ids=profile.department_ids,
        user_primary_department_id=profile.primary_department_id,
        chat_department_ids=[UUID(d) for d in (tmpl.get("department_ids") or [])],
    )

    # Extract template state
    t_persona_ids = [UUID(x) for x in (tmpl.get("persona_ids") or [])]
    t_document_ids = [UUID(x) for x in (tmpl.get("document_ids") or [])]
    t_name_ids = [UUID(x) for x in (tmpl.get("name_ids") or [])]
    t_description_ids = [UUID(x) for x in (tmpl.get("description_ids") or [])]
    t_problem_statement_ids = [UUID(x) for x in (tmpl.get("problem_statement_ids") or [])]
    t_objective_ids = [UUID(x) for x in (tmpl.get("objective_ids") or [])]
    t_question_ids = [UUID(x) for x in (tmpl.get("question_ids") or [])]
    t_option_ids = [UUID(x) for x in (tmpl.get("option_ids") or [])]
    t_video_ids = [UUID(x) for x in (tmpl.get("video_ids") or [])]
    t_image_ids = [UUID(x) for x in (tmpl.get("image_ids") or [])]
    t_parameter_field_ids = [UUID(x) for x in (tmpl.get("parameter_field_ids") or [])]
    t_rubric_ids = [UUID(x) for x in (tmpl.get("rubric_ids") or [])]
    t_standard_ids = [UUID(x) for x in (tmpl.get("standard_ids") or [])]
    t_standard_group_ids = [UUID(x) for x in (tmpl.get("standard_group_ids") or [])]

    # Scenario flags
    questions_enabled = tmpl.get("questions_enabled") or False
    video_enabled = tmpl.get("video_enabled") or False
    images_enabled = tmpl.get("images_enabled") or False
    problem_statement_enabled = tmpl.get("problem_statement_enabled") or False
    objectives_enabled = tmpl.get("objectives_enabled") or False

    # Config flags — all from template
    cfg_audio_enabled = tmpl.get("audio_enabled", False) or False
    cfg_text_enabled = tmpl.get("text_enabled", True)
    cfg_hints_enabled = tmpl.get("hints_enabled", False) or False
    cfg_copy_paste_allowed = tmpl.get("copy_paste_allowed", True)
    cfg_show_images = tmpl.get("show_images", False) or False
    cfg_show_objectives = tmpl.get("show_objectives", False) or False
    cfg_show_problem_statement = tmpl.get("show_problem_statement", False) or False
    cfg_analyses_enabled = tmpl.get("analyses_enabled", False) or False
    cfg_improvements_enabled = tmpl.get("improvements_enabled", False) or False
    cfg_strengths_enabled = tmpl.get("strengths_enabled", False) or False
    cfg_use_custom = tmpl.get("use_custom", False) or False
    cfg_use_previous = tmpl.get("use_previous", False) or False
    cfg_time_limit = tmpl.get("time_limit")
    cfg_negative_time = tmpl.get("negative_time", False) or False
    cfg_position = tmpl.get("position", 0) or 0
    cfg_name = tmpl.get("name", "") or ""

    # ── Step 3: Resolve values ────────────────────────────────────────────────

    from app.tools.resources.names.create import create_name
    from app.tools.resources.descriptions.create import create_description
    from app.tools.resources.problem_statements.create import create_problem_statement
    from app.tools.resources.objectives.create import create_objective
    from app.tools.resources.questions.create import create_question
    from app.tools.resources.options.create import create_option
    from app.tools.resources.personas.search import search_personas
    from app.tools.resources.parameter_fields.search import search_parameter_fields
    from app.tools.resources.documents.search import search_documents

    scope_dept_ids = [department_id] if department_id else profile.department_ids

    async with pool.acquire() as conn:
        # Single-select text resources (create if value provided)
        resolved_name_id = await _resolve_single_text(
            conn, redis, resource_id=request.name_id, value=request.name,
            label="name", create_fn=create_name, create_kwarg="name",
        )
        resolved_description_id = await _resolve_single_text(
            conn, redis, resource_id=request.description_id, value=request.description,
            label="description", create_fn=create_description, create_kwarg="description",
        )
        # Problem statement needs both name + text for create
        resolved_problem_statement_id: UUID | None = None
        if request.problem_statement_id and request.problem_statement:
            raise HTTPException(400, "Pass problem_statement_id or problem_statement, not both.")
        elif request.problem_statement_id:
            resolved_problem_statement_id = request.problem_statement_id
        elif request.problem_statement:
            ps = await create_problem_statement(
                conn, name=request.problem_statement[:80],
                problem_statement=request.problem_statement, redis=redis,
            )
            resolved_problem_statement_id = ps.id

        # Multi-select complex resources (search by name, error if not found)
        resolved_personas_ids = await _resolve_multi_search(
            conn, redis, ids=request.personas_ids, values=request.personas,
            label="persona", search_fn=search_personas, department_ids=scope_dept_ids,
        )
        resolved_documents_ids = await _resolve_multi_search(
            conn, redis, ids=request.documents_ids, values=request.documents,
            label="document", search_fn=search_documents, department_ids=scope_dept_ids,
        )

        # Parameter fields — resolve by field name lookup
        resolved_parameter_fields_ids: list[UUID] | None = request.parameter_fields_ids
        if request.parameter_fields_ids and request.parameter_fields:
            raise HTTPException(400, "Pass parameter_fields_ids or parameter_fields, not both.")
        if request.parameter_fields:
            from app.tools.resources.fields.search import search_fields
            resolved_parameter_fields_ids = []
            seen_pf_ids: set[UUID] = set()
            for field_name in request.parameter_fields:
                # Search fields by exact name first, fall back to ILIKE
                fields = await search_fields(
                    conn, redis, search=field_name, limit_count=5, bypass_cache=True,
                )
                # Prefer exact match
                exact = [f for f in fields if f.name == field_name]
                field = exact[0] if exact else (fields[0] if fields else None)
                if not field:
                    all_fields = await search_fields(conn, redis, limit_count=50, bypass_cache=True)
                    available = [f.name for f in all_fields if f.name]
                    hint = f"Available: {', '.join(available[:20])}" if available else "No fields available"
                    raise HTTPException(400, f'Field not found: "{field_name}". {hint}')
                # Find the parameter_field linking this field
                pfs = await search_parameter_fields(
                    conn, redis, field_ids=[field.id], limit_count=1, bypass_cache=True,
                )
                if not pfs:
                    raise HTTPException(400, f'No parameter field for field: "{field_name}"')
                # Deduplicate
                if pfs[0].id not in seen_pf_ids:
                    seen_pf_ids.add(pfs[0].id)
                    resolved_parameter_fields_ids.append(pfs[0].id)

        # Multi-select text resources (create if value provided)
        resolved_objectives_ids = await _resolve_multi_text(
            conn, redis, ids=request.objectives_ids, values=request.objectives,
            label="objective", create_fn=create_objective, create_kwarg="objective",
        )

        # Questions with nested options
        resolved_questions_ids: list[UUID] | None = request.questions_ids
        resolved_options_ids: list[UUID] | None = request.options_ids
        if request.questions_ids and request.questions:
            raise HTTPException(400, "Pass questions_ids or questions, not both.")
        if request.questions:
            resolved_questions_ids = []
            created_option_ids: list[UUID] = []
            for qv in request.questions:
                q = await create_question(
                    conn, question_text=qv.question_text, time=30,
                    allow_multiple=qv.allow_multiple, redis=redis,
                )
                resolved_questions_ids.append(q.id)
                if qv.options:
                    for ov in qv.options:
                        o = await create_option(
                            conn, option_text=ov.option_text, question_id=q.id,
                            is_correct=ov.is_correct, redis=redis,
                        )
                        created_option_ids.append(o.id)
            # Merge inline-created options with any standalone options_ids
            if created_option_ids:
                resolved_options_ids = (resolved_options_ids or []) + created_option_ids

    # ── Step 4: Validate ──────────────────────────────────────────────────────

    has_questions = bool(resolved_questions_ids or request.questions)
    has_options = bool(resolved_options_ids)
    has_video = bool(request.video_id or t_video_ids)

    # Mode gating — video_enabled is the master toggle
    if video_enabled:
        # Video mode: video → questions → options
        if request.image_id:
            raise HTTPException(400, "Images are for chat mode (non-video). Use video_id instead.")
        if has_questions and not has_video:
            raise HTTPException(400, "Questions require a video — pass video_id.")
        if has_options and not has_questions and not t_question_ids:
            raise HTTPException(400, "Options require questions — pass questions or questions_ids first.")
    else:
        # Chat mode: no video/questions/options
        if request.video_id:
            raise HTTPException(400, "Video is not enabled for this chat (chat mode).")
        if has_questions:
            raise HTTPException(400, "Questions require video mode (video_enabled must be true).")
        if has_options:
            raise HTTPException(400, "Options require video mode (video_enabled must be true).")

    # Independent flag gating
    if not problem_statement_enabled and (resolved_problem_statement_id or request.problem_statement_id):
        raise HTTPException(400, "Problem statements are not enabled for this chat.")
    if not objectives_enabled and resolved_objectives_ids:
        raise HTTPException(400, "Objectives are not enabled for this chat.")

    # Pre-satisfied locking — reject if template already has resources
    if t_persona_ids and resolved_personas_ids:
        raise HTTPException(400, "Personas are already configured on the chat template.")
    if t_document_ids and resolved_documents_ids:
        raise HTTPException(400, "Documents are already configured on the chat template.")
    if t_problem_statement_ids and resolved_problem_statement_id:
        raise HTTPException(400, "Problem statements are already configured on the chat template.")
    if t_objective_ids and resolved_objectives_ids:
        raise HTTPException(400, "Objectives are already configured on the chat template.")
    if t_question_ids and resolved_questions_ids:
        raise HTTPException(400, "Questions are already configured on the chat template.")
    if t_option_ids and resolved_options_ids:
        raise HTTPException(400, "Options are already configured on the chat template.")
    if t_video_ids and request.video_id:
        raise HTTPException(400, "Video is already configured on the chat template.")
    if t_image_ids and request.image_id:
        raise HTTPException(400, "Image is already configured on the chat template.")

    # ── Step 5: Merge — template pre-set + model selections + auto ────────────

    final_departments_ids = [department_id] if department_id else []
    final_names_ids = t_name_ids or ([resolved_name_id] if resolved_name_id else None)
    final_descriptions_ids = t_description_ids or ([resolved_description_id] if resolved_description_id else None)
    final_personas_ids = t_persona_ids or resolved_personas_ids
    final_documents_ids = t_document_ids or resolved_documents_ids
    final_problem_statements_ids = t_problem_statement_ids or ([resolved_problem_statement_id] if resolved_problem_statement_id else None)
    final_objectives_ids = t_objective_ids or resolved_objectives_ids
    final_questions_ids = t_question_ids or resolved_questions_ids
    final_options_ids = t_option_ids or resolved_options_ids
    final_videos_ids = t_video_ids or ([request.video_id] if request.video_id else None)
    final_images_ids = t_image_ids or ([request.image_id] if request.image_id else None)
    final_parameter_fields_ids = t_parameter_field_ids or resolved_parameter_fields_ids

    # ── Step 6: Create in transaction ─────────────────────────────────────────

    from app.tools.entries.persona.create import create_persona

    async with pool.acquire() as conn:
        async with conn.transaction():
            # Create personas_entry for each AI persona resource ID
            assistant_entry_ids: list[UUID] = []
            for persona_resource_id in (final_personas_ids or []):
                persona_entry = await create_persona(
                    conn, personas_id=persona_resource_id,
                )
                assistant_entry_ids.append(persona_entry.id)

            result = await create_attempt_chat(
                conn,
                session_id=session_id,
                chat_id=request.chat_id,
                title=cfg_name,
                position=cfg_position,
                time_limit=cfg_time_limit,
                negative_time=cfg_negative_time,
                audio_enabled=cfg_audio_enabled,
                text_enabled=cfg_text_enabled,
                hints_enabled=cfg_hints_enabled,
                copy_paste_allowed=cfg_copy_paste_allowed,
                show_images=cfg_show_images,
                show_objectives=cfg_show_objectives,
                show_problem_statement=cfg_show_problem_statement,
                analyses_enabled=cfg_analyses_enabled,
                improvements_enabled=cfg_improvements_enabled,
                strengths_enabled=cfg_strengths_enabled,
                use_custom=cfg_use_custom,
                use_previous=cfg_use_previous,
                problem_statement_enabled=problem_statement_enabled,
                objectives_enabled=objectives_enabled,
                video_enabled=video_enabled,
                images_enabled=images_enabled,
                questions_enabled=questions_enabled,
                rubrics_ids=t_rubric_ids or None,
                standards_ids=t_standard_ids or None,
                standard_groups_ids=t_standard_group_ids or None,
                departments_ids=final_departments_ids,
                assistant_persona_ids=assistant_entry_ids or None,
                personas_ids=final_personas_ids,
                problem_statements_ids=final_problem_statements_ids,
                objectives_ids=final_objectives_ids,
                questions_ids=final_questions_ids,
                options_ids=final_options_ids,
                videos_ids=final_videos_ids,
                images_ids=final_images_ids,
                documents_ids=final_documents_ids,
                parameter_fields_ids=final_parameter_fields_ids,
                names_ids=final_names_ids,
                descriptions_ids=final_descriptions_ids,
                soft=soft,
            )
            await create_attempt_chat_bridge(
                conn,
                attempt_id=request.attempt_id,
                attempt_chat_id=result.id,
                session_id=session_id,
                soft=soft,
            )

    # ── Step 7: Refresh + return ──────────────────────────────────────────────

    async with pool.acquire() as conn:
        await refresh_attempt_chat(conn)
        await refresh_attempt_chat_bridge(conn)

    return CreateAttemptChatApiResponse(
        attempt_chat_id=result.id,
        idempotency_key=request.idempotency_key,
    )
