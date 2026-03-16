"""Scenario draft logic — composable infra architecture.

Core draft function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_draft — permission check
  3. Value resolution (creatable resources only) — raw value → ID
  4. create_scenario_draft — entry tool (append-only snapshot)
  5. refresh_scenario_drafts — MV refresh
  6. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.scenario.permissions import compute_can_draft
from app.infra.scenario.types import (
    PatchScenarioDraftApiRequest,
    PatchScenarioDraftApiResponse,
    SaveScenarioFieldError,
    ScenarioDraftFormState,
)
from app.tools.entries.scenario_drafts.create import create_scenario_draft
from app.tools.entries.scenario_drafts.refresh import refresh_scenario_drafts
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.images.create import create_image
from app.tools.resources.names.create import create_name
from app.tools.resources.objectives.create import create_objective
from app.tools.resources.options.create import create_option
from app.tools.resources.problem_statements.create import (
    create_problem_statement,
)
from app.tools.resources.questions.create import create_question
from app.tools.resources.videos.create import create_video
from app.utils.cache.invalidate_tags import invalidate_tags

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
    request: PatchScenarioDraftApiRequest,
) -> PatchScenarioDraftApiResponse:
    """Scenario draft using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role
      2. compute_can_draft → permission check
      3. Value resolution (creatable resources only)
      4. create_scenario_draft entry tool (append-only snapshot)
      5. refresh_scenario_drafts MV
      6. invalidate_tags
    """

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(
        pool,
        profile_id,
        redis,
        session_id=session_id,
    )

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Permission check ───────────────────────────────────────

    if not compute_can_draft(user_role=profile.role):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create or edit scenario drafts.",
        )

    # ── Step 3: Value resolution (creatable only) ──────────────────────

    errors = await _resolve_creatable_values(pool, redis, request)
    if errors:
        raise HTTPException(
            status_code=400,
            detail=[e.model_dump() for e in errors],
        )

    # ── Step 4: Create draft entry (append-only snapshot) ──────────────

    # Compute new version
    new_version = request.expected_version + 1

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_scenario_draft(
                conn,
                group_id=profile.group_id,
                session_id=session_id,
                version=new_version,
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
            )

    # ── Step 5: Build form state (server is source of truth) ──────────

    form_state = ScenarioDraftFormState(
        name_id=request.name_id,
        description_id=request.description_id,
        problem_statement_id=request.problem_statement_id,
        flag_ids=request.flag_ids or [],
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

    # ── Step 6: Refresh MV ─────────────────────────────────────────────

    async with pool.acquire() as conn:
        await refresh_scenario_drafts(conn)

    # ── Step 7: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["scenarios", "drafts"], redis=redis)

    return PatchScenarioDraftApiResponse(
        success=True,
        draft_id=result.id,
        new_version=new_version,
        message="Draft created successfully",
        form_state=form_state,
    )
