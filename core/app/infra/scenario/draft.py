"""Scenario draft logic — composable infra architecture.

Core draft function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_draft — permission check
  3. Value resolution (creatable resources only) — raw value → ID
  4. create_scenario_draft — entry tool (append-only snapshot)
 5. refresh_scenario_impl — MV refresh + cache invalidation
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.drafts.ownership import enforce_draft_owner
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.scenario.permissions import compute_can_draft
from app.infra.server_timing import timed
from app.infra.scenario.refresh import refresh_scenario_impl
from app.infra.scenario.types import (
    PatchScenarioDraftApiRequest,
    PatchScenarioDraftApiResponse,
    SaveScenarioFieldError,
    ScenarioDraftFormState,
)
from app.infra.tools.sanitize import sanitize_model_kwargs
from app.tools.entries.scenario_drafts.create import create_scenario_draft
from app.tools.entries.scenario_drafts.get import get_scenario_drafts
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.entries.soft_calls.search import search_soft_calls
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.flags.search import search_flags
from app.tools.resources.images.create import create_image
from app.tools.resources.names.create import create_name
from app.tools.resources.objectives.create import create_objective
from app.tools.resources.options.create import create_option
from app.tools.resources.problem_statements.create import (
    create_problem_statement,
)
from app.tools.resources.questions.create import create_question
from app.tools.resources.videos.create import create_video

ARTIFACT = "scenario"
OPERATION = "draft"


async def _maybe_auto_accept_scenario_draft(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    draft_id: UUID,
    session_id: UUID,
    profile_ids: list[UUID],
) -> bool:
    """Auto-accept the draft when no pending fields remain. Mirrors persona/draft.py."""
    async with pool.acquire() as conn:
        ledger_entries = await search_soft_calls(
            conn,
            redis,
            artifact=ARTIFACT,
            operation=OPERATION,
            artifact_ids=[draft_id],
            status="pending",
            limit=1,
        )
    if not ledger_entries:
        return False
    call_id = ledger_entries[0].call_id

    async with pool.acquire() as conn:
        drafts = await get_scenario_drafts(conn, [draft_id], redis, active=None)
    if not drafts:
        return False
    draft = drafts[0]
    pending_lists = [
        getattr(draft, "pending_name_ids", None),
        getattr(draft, "pending_description_ids", None),
        getattr(draft, "pending_problem_statement_ids", None),
        getattr(draft, "pending_department_ids", None),
        getattr(draft, "pending_persona_ids", None),
        getattr(draft, "pending_document_ids", None),
        getattr(draft, "pending_objective_ids", None),
        getattr(draft, "pending_image_ids", None),
        getattr(draft, "pending_video_ids", None),
        getattr(draft, "pending_question_ids", None),
        getattr(draft, "pending_option_ids", None),
        getattr(draft, "pending_flag_ids", None),
        getattr(draft, "pending_parameter_field_ids", None),
    ]
    if any(pl for pl in pending_lists if pl):
        return False

    async with pool.acquire() as conn:
        async with conn.transaction():
            await create_scenario_draft(
                conn,
                redis, session_id=session_id,
                id=draft_id,
                soft=False,
                name_ids=draft.name_ids,
                description_ids=draft.description_ids,
                problem_statement_ids=draft.problem_statement_ids,
                flag_ids=draft.flag_ids,
                department_ids=draft.department_ids,
                persona_ids=draft.persona_ids,
                document_ids=draft.document_ids,
                parameter_field_ids=draft.parameter_field_ids,
                objective_ids=draft.objective_ids,
                image_ids=draft.image_ids,
                video_ids=draft.video_ids,
                question_ids=draft.question_ids,
                option_ids=draft.option_ids,
                profile_ids=draft.profile_ids or profile_ids,
                pending_ids=set(),
            )
            await create_soft_call(
                conn,
                redis,
                call_id=call_id,
                artifact=ARTIFACT,
                operation=OPERATION,
                artifact_id=draft_id,
                status="accepted",
            )
    async with pool.acquire() as conn:
        await refresh_soft_calls(conn)
    return True


# Denormalized bool field name → flag type in flags_resource.
SCENARIO_DENORM_FLAG_FIELDS = {
    "active": "scenario_active",
    "video_enabled": "video_enabled",
    "problem_statement_enabled": "problem_statement_enabled",
    "objectives_enabled": "objectives_enabled",
    "images_enabled": "images_enabled",
    "questions_enabled": "questions_enabled",
}

# ---------------------------------------------------------------------------
# Value resolution — creatable resources only
# ---------------------------------------------------------------------------


async def _resolve_creatable_values(
    pool: asyncpg.Pool,
    redis: Redis,
    request: PatchScenarioDraftApiRequest,
) -> list[SaveScenarioFieldError]:
    """Resolve raw value fields to resource IDs (mutates request in place).

    Single-select creatables: name, description, problem_statement
      → value creates resource, ID replaces value (mutually exclusive).

    Multi-select creatables: objectives, images, videos, questions, options
      → values create resources, created IDs are merged with existing IDs.

    Returns a list of errors (empty if all resolved).
    """
    errors: list[SaveScenarioFieldError] = []

    async with pool.acquire() as conn:
        # ── Single-select creatables ──────────────────────────────────────

        if request.name is not None and request.name_id is None:
            result = await create_name(conn, request.name, redis)
            request.name_id = result.id

        if request.description is not None and request.description_id is None:
            result = await create_description(conn, request.description, redis)
            request.description_id = result.id

        if (
            request.problem_statement is not None
            and request.problem_statement_id is None
        ):
            result = await create_problem_statement(
                conn, request.name or "", request.problem_statement, redis
            )
            request.problem_statement_id = result.id

        # ── Multi-select creatables (merged mode) ─────────────────────────

        if request.objectives:
            created_ids = []
            for obj_text in request.objectives:
                result = await create_objective(conn, obj_text, redis)
                created_ids.append(result.id)
            request.objective_ids = (request.objective_ids or []) + created_ids

        if request.images:
            created_ids = []
            for img in request.images:
                result = await create_image(conn, img.name, img.description, redis)
                created_ids.append(result.id)
            request.image_ids = (request.image_ids or []) + created_ids

        if request.videos:
            created_ids = []
            for vid in request.videos:
                result = await create_video(conn, vid.name, vid.description, redis)
                created_ids.append(result.id)
            request.video_ids = (request.video_ids or []) + created_ids

        if request.questions:
            created_ids = []
            for q in request.questions:
                result = await create_question(
                    conn,
                    q.question_text,
                    q.time,
                    redis,
                    allow_multiple=q.allow_multiple,
                )
                created_ids.append(result.id)
            request.question_ids = (request.question_ids or []) + created_ids

        if request.options:
            created_ids = []
            for opt in request.options:
                result = await create_option(
                    conn, opt.option_text, redis, question_id=opt.question_id
                )
                created_ids.append(result.id)
            request.option_ids = (request.option_ids or []) + created_ids

    # Denorm bool → flag_ids via (type, value) lookup in flags_resource.
    denorm_values: dict[str, bool] = {}
    for field_name, flag_type in SCENARIO_DENORM_FLAG_FIELDS.items():
        v = getattr(request, field_name, None)
        if v is not None:
            denorm_values[flag_type] = bool(v)
    if denorm_values:
        async with pool.acquire() as conn:
            all_rows = await search_flags(
                conn, redis, search=None, limit_count=200, bypass_cache=True
            )
        resolved_ids: list[UUID] = list(request.flag_ids or [])
        seen = set(resolved_ids)
        for ftype, desired in denorm_values.items():
            match = next(
                (
                    f
                    for f in all_rows
                    if (getattr(f, "type", None) == ftype
                        or getattr(f, "name", None) == ftype)
                    and getattr(f, "value", None) is desired
                ),
                None,
            )
            if match and match.id and match.id not in seen:
                resolved_ids.append(match.id)
                seen.add(match.id)
        request.flag_ids = resolved_ids

    return errors


# ---------------------------------------------------------------------------
# patch_scenario_draft_impl — composable infra architecture
# ---------------------------------------------------------------------------


async def patch_scenario_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchScenarioDraftApiRequest | None = None,
    draft_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **kwargs: Any,
) -> PatchScenarioDraftApiResponse:
    """Scenario draft using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role
      2. compute_can_draft → permission check
      3. Value resolution (creatable resources only)
      4. create_scenario_draft entry tool (append-only snapshot)
      5. refresh_scenario_impl MV + cache invalidation
    """

    # ── Merge ack fields from request (HTTP) or params (generation pipeline)
    if request is not None:
        idempotency_key = idempotency_key or request.idempotency_key
        if idempotency_key and accept is None:
            accept = request.accept

    # ── Profile context (canonical: resolved BEFORE the ack short-circuit
    # so the ack branch can use ``profile.profiles_id`` without an inline
    # workaround). Mirrors persona/draft.py.
    with timed("profile"):
        profile = await resolve_profile_identity_context(
            pool, profile_id, redis, session_id=session_id,
        )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Short-circuit: ack path ───────────────────────────────────────
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(
                status_code=404,
                detail="No pending scenario draft for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            owner_profile_id = profile.profiles_id
            async with pool.acquire() as conn:
                await enforce_draft_owner(
                    conn,
                    redis,
                    draft_id=target_id,
                    getter=get_scenario_drafts,
                    caller_session_id=session_id,
                    caller_profile_id=profile.profiles_id,
                    role_level=profile.role_level,
                    artifact=ARTIFACT,
                )
                drafts = await get_scenario_drafts(conn, [target_id], redis, active=None)
                async with conn.transaction():
                    if drafts:
                        draft = drafts[0]
                        await create_scenario_draft(
                            conn,
                            redis, session_id=session_id,
                            id=target_id,
                            soft=False,
                            name_ids=draft.name_ids,
                            description_ids=draft.description_ids,
                            problem_statement_ids=draft.problem_statement_ids,
                            flag_ids=draft.flag_ids,
                            department_ids=draft.department_ids,
                            persona_ids=draft.persona_ids,
                            document_ids=draft.document_ids,
                            parameter_field_ids=draft.parameter_field_ids,
                            objective_ids=draft.objective_ids,
                            image_ids=draft.image_ids,
                            video_ids=draft.video_ids,
                            question_ids=draft.question_ids,
                            option_ids=draft.option_ids,
                            profile_ids=draft.profile_ids or [owner_profile_id],
                            pending_ids=set(),
                        )
                    else:
                        await create_scenario_draft(
                            conn,
                            redis, session_id=session_id,
                            id=target_id,
                            soft=False,
                            profile_ids=[owner_profile_id],
                        )

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                redis,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation=OPERATION,
                artifact_id=target_id,
                status="accepted" if accept else "rejected",
            )
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

        await refresh_scenario_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            targets=["scenario_drafts_mv"],
            operation_key=idempotency_key,
        )
        return PatchScenarioDraftApiResponse(
            success=True,
            draft_id=target_id,
            idempotency_key=idempotency_key,
            message="Draft accepted" if accept else "Draft rejected",
            form_state=ScenarioDraftFormState(
                name_id=None,
                description_id=None,
                problem_statement_id=None,
                flag_ids=[],
                department_ids=[],
                persona_ids=[],
                document_ids=[],
                parameter_field_ids=[],
                objective_ids=[],
                image_ids=[],
                video_ids=[],
                question_ids=[],
                option_ids=[],
            ),
        )

    # Build request from kwargs if not provided directly
    if request is None:
        filtered = sanitize_model_kwargs(
            kwargs,
            list_fields={
                "flag_ids",
                "department_ids",
                "persona_ids",
                "document_ids",
                "parameter_field_ids",
                "objective_ids",
                "objectives",
                "image_ids",
                "images",
                "video_ids",
                "videos",
                "question_ids",
                "questions",
                "option_ids",
                "options",
                "pending_ids",
            },
            value_id_pairs=[
                ("name", "name_id"),
                ("description", "description_id"),
                ("problem_statement", "problem_statement_id"),
            ],
        )
        if draft_id:
            filtered["input_draft_id"] = draft_id
        request = PatchScenarioDraftApiRequest(**filtered)

    # ── Step 1: Profile context — already resolved at top.

    # ── Step 2: Permission check ───────────────────────────────────────

    with timed("permissions"):
        if not compute_can_draft(role_level=profile.role_level, role_permissions=profile.role_permissions):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to create or edit scenario drafts.",
            )

    # ── Step 3: Value resolution (creatable only) ──────────────────────

    with timed("resolve_values"):
        errors = await _resolve_creatable_values(pool, redis, request)
    if errors:
        raise HTTPException(
            status_code=400,
            detail=[e.model_dump() for e in errors],
        )

    # ── Step 4: Create draft entry (append-only snapshot) ──────────────

    with timed("db_write"):
      async with pool.acquire() as conn:
        await enforce_draft_owner(
            conn,
            redis,
            draft_id=idempotency_key,
            getter=get_scenario_drafts,
            caller_session_id=session_id,
            caller_profile_id=profile.profiles_id,
            role_level=profile.role_level,
            artifact=ARTIFACT,
        )
        async with conn.transaction():
            result = await create_scenario_draft(
                conn,
                redis, session_id=session_id,
                id=idempotency_key,
                soft=soft,
                name=request.name or "",
                name_ids=[request.name_id] if request.name_id else None,
                description_ids=[request.description_id]
                if request.description_id
                else None,
                problem_statement_ids=[request.problem_statement_id]
                if request.problem_statement_id
                else None,
                flag_ids=request.flag_ids,
                department_ids=request.department_ids,
                persona_ids=request.persona_ids,
                document_ids=request.document_ids,
                parameter_field_ids=request.parameter_field_ids,
                objective_ids=request.objective_ids,
                image_ids=request.image_ids,
                video_ids=request.video_ids,
                question_ids=request.question_ids,
                option_ids=request.option_ids,
                pending_ids=set(request.pending_ids) if request.pending_ids else None,
                profile_ids=[profile.profiles_id],
            )

            if soft and idempotency_key is not None:
                await create_soft_call(
                    conn,
                    redis,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation=OPERATION,
                    artifact_id=result.id,
                )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    # ── Auto-accept merge step: if no pending fields remain and a
    # pending soft_calls_entry exists for this draft, promote it.
    if not soft:
        await _maybe_auto_accept_scenario_draft(
            pool, redis,
            draft_id=result.id,
            session_id=session_id,
            profile_ids=[profile.profiles_id],
        )

    # ── Step 5: Build form state (server is source of truth) ──────────

    # Re-derive denormalized bools from final flag_ids so the client echo
    # mirrors what the server actually persisted.
    echoed_bools: dict[str, bool | None] = {
        f: getattr(request, f, None) for f in SCENARIO_DENORM_FLAG_FIELDS
    }
    if request.flag_ids:
        async with pool.acquire() as conn:
            flag_rows = await search_flags(
                conn, redis, search=None, limit_count=200, bypass_cache=True
            )
        rows_by_id = {row.id: row for row in flag_rows if getattr(row, "id", None)}
        type_to_field = {v: k for k, v in SCENARIO_DENORM_FLAG_FIELDS.items()}
        for fid in request.flag_ids:
            row = rows_by_id.get(fid)
            if not row:
                continue
            rtype = getattr(row, "type", None) or getattr(row, "name", None)
            field = type_to_field.get(rtype or "")
            if field:
                echoed_bools[field] = getattr(row, "value", None)

    form_state = ScenarioDraftFormState(
        name_id=request.name_id,
        description_id=request.description_id,
        problem_statement_id=request.problem_statement_id,
        flag_ids=request.flag_ids or [],
        active=echoed_bools.get("active"),
        video_enabled=echoed_bools.get("video_enabled"),
        problem_statement_enabled=echoed_bools.get("problem_statement_enabled"),
        objectives_enabled=echoed_bools.get("objectives_enabled"),
        images_enabled=echoed_bools.get("images_enabled"),
        questions_enabled=echoed_bools.get("questions_enabled"),
        department_ids=request.department_ids or [],
        persona_ids=request.persona_ids or [],
        document_ids=request.document_ids or [],
        parameter_field_ids=request.parameter_field_ids or [],
        objective_ids=request.objective_ids or [],
        image_ids=request.image_ids or [],
        video_ids=request.video_ids or [],
        question_ids=request.question_ids or [],
        option_ids=request.option_ids or [],
    )

    # ── Step 5: Refresh MV + cache invalidation ────────────────────────

    with timed("refresh"):
        await refresh_scenario_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            targets=["scenario_drafts_mv"],
            soft=soft,
            name=request.name or "",
            operation_key=idempotency_key or result.id,
        )

    return PatchScenarioDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=idempotency_key or result.id,
        message="Draft created (pending acceptance)" if soft else "Draft created successfully",
        form_state=form_state,
    )
