"""Cohort draft logic — composable infra architecture.

Core draft function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_draft — permission check
  3. Value resolution (creatable resources only) — raw value → ID
  4. create_cohort_draft — entry tool (append-only snapshot)
  5. Build form state (server is source of truth)
  6. refresh_cohort_drafts — MV refresh
  7. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.cohort.permissions import compute_can_draft
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.cohort.types import (
    CohortDraftFormState,
    PatchCohortDraftApiRequest,
    PatchCohortDraftApiResponse,
    SaveCohortFieldError,
)
from app.tools.entries.cohort_drafts.create import create_cohort_draft
from app.tools.entries.cohort_drafts.refresh import refresh_cohort_drafts
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.names.create import create_name
from app.tools.resources.profile_personas.create import create_profile_persona
from app.tools.resources.simulation_availability.create import (
    create_simulation_availability,
)
from app.tools.resources.simulation_positions.create import (
    create_simulation_position as create_sim_position,
)
from app.utils.cache.invalidate_tags import invalidate_tags

# ---------------------------------------------------------------------------
# Value resolution — creatable resources only
# ---------------------------------------------------------------------------


async def _resolve_creatable_values(
    pool: asyncpg.Pool,
    redis: Redis,
    request: PatchCohortDraftApiRequest,
) -> list[SaveCohortFieldError]:
    """Resolve raw value fields to resource IDs (mutates request in place).

    Single-select creatables: name, description
      → value creates resource, ID replaces value (mutually exclusive).

    Multi-select compound creatables: simulation_positions, simulation_availability,
      profile_personas
      → values create resources, created IDs are merged with existing IDs.

    Returns a list of errors (empty if all resolved).
    """
    errors: list[SaveCohortFieldError] = []

    # ── Single-select creatables ──────────────────────────────────────

    async with pool.acquire() as conn:
        if request.name is not None and request.name_id is None:
            result = await create_name(conn, request.name, redis)
            request.name_id = result.id

        if request.description is not None and request.description_id is None:
            result = await create_description(conn, request.description, redis)
            request.description_id = result.id

        # ── Multi-select compound creatables (merged mode) ────────────────

        if request.simulation_positions:
            created_ids = []
            for sp in request.simulation_positions:
                result = await create_sim_position(
                    conn, sp.simulation_id, sp.value, redis
                )
                created_ids.append(result.id)
            request.simulation_position_ids = (
                request.simulation_position_ids or []
            ) + created_ids

        if request.simulation_availability:
            created_ids = []
            for sa in request.simulation_availability:
                result = await create_simulation_availability(
                    conn, sa.simulation_id, sa.time, sa.type, redis
                )
                created_ids.append(result.id)
            request.simulation_availability_ids = (
                request.simulation_availability_ids or []
            ) + created_ids

        if request.profile_personas:
            created_ids = []
            for pp in request.profile_personas:
                result = await create_profile_persona(
                    conn, pp.profile_id, pp.persona_id, redis
                )
                created_ids.append(result.id)
            request.profile_persona_ids = (
                request.profile_persona_ids or []
            ) + created_ids

    return errors


# ---------------------------------------------------------------------------
# patch_cohort_draft_impl — composable infra architecture
# ---------------------------------------------------------------------------


async def patch_cohort_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchCohortDraftApiRequest,
) -> PatchCohortDraftApiResponse:
    """Cohort draft using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role
      2. compute_can_draft → permission check
      3. Value resolution (creatable resources only)
      4. create_cohort_draft entry tool (append-only snapshot)
      5. Build form state (server is source of truth)
      6. refresh_cohort_drafts MV
      7. invalidate_tags
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
            detail="You don't have permission to create or edit cohort drafts.",
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
            result = await create_cohort_draft(
                conn,
                group_id=profile.group_id,
                session_id=session_id,
                version=new_version,
                name_ids=[request.name_id] if request.name_id else None,
                description_ids=[request.description_id]
                if request.description_id
                else None,
                flag_ids=[request.flag_id] if request.flag_id else None,
                department_ids=request.department_ids,
                simulation_ids=request.simulation_ids,
                profile_ids=request.profile_ids,
                profile_persona_ids=request.profile_persona_ids,
                simulation_availability_ids=request.simulation_availability_ids,
                simulation_position_ids=request.simulation_position_ids,
            )

    # ── Step 5: Build form state (server is source of truth) ──────────

    form_state = CohortDraftFormState(
        name_id=request.name_id,
        description_id=request.description_id,
        flag_id=request.flag_id,
        department_ids=request.department_ids or [],
        simulation_ids=request.simulation_ids or [],
        simulation_position_ids=request.simulation_position_ids or [],
        simulation_availability_ids=request.simulation_availability_ids or [],
        profile_ids=request.profile_ids or [],
        profile_persona_ids=request.profile_persona_ids or [],
    )

    # ── Step 6: Refresh MV ─────────────────────────────────────────────

    async with pool.acquire() as conn:
        await refresh_cohort_drafts(conn)

    # ── Step 7: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["cohorts", "drafts"], redis=redis)

    return PatchCohortDraftApiResponse(
        success=True,
        draft_id=result.id,
        new_version=new_version,
        message="Draft created successfully",
        form_state=form_state,
    )
