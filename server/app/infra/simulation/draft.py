"""Simulation draft logic — composable infra architecture.

Core draft function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_draft — permission check
  3. Value resolution (creatable resources only) — raw value → ID
  4. create_simulation_draft — entry tool (append-only snapshot)
  5. Build form state (server is source of truth)
  6. refresh_simulation_drafts — MV refresh
  7. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.simulation.permissions import compute_can_draft
from app.infra.simulation.types import (
    PatchSimulationDraftApiRequest,
    PatchSimulationDraftApiResponse,
    SaveSimulationFieldError,
    SimulationDraftFormState,
)
from app.tools.entries.simulation_drafts.create import (
    create_simulation_draft,
)
from app.tools.entries.simulation_drafts.refresh import (
    refresh_simulation_drafts,
)
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.names.create import create_name
from app.tools.resources.scenario_flags.create import create_scenario_flag
from app.tools.resources.scenario_positions.create import (
    create_scenario_position,
)
from app.tools.resources.scenario_rubrics.create import create_scenario_rubric
from app.tools.resources.scenario_time_limits.create import (
    create_scenario_time_limit,
)
from app.utils.cache.invalidate_tags import invalidate_tags

# ---------------------------------------------------------------------------
# Value resolution — creatable resources only
# ---------------------------------------------------------------------------


async def _resolve_creatable_values(
    pool: asyncpg.Pool,
    redis: Redis,
    request: PatchSimulationDraftApiRequest,
) -> list[SaveSimulationFieldError]:
    """Resolve raw value fields to resource IDs (mutates request in place).

    Single-select creatables: name, description
      → value creates resource, ID replaces value (mutually exclusive).

    Multi-select compound creatables: scenario_flags, scenario_positions,
      scenario_rubrics, scenario_time_limits
      → values create resources, created IDs are merged with existing IDs.

    Returns a list of errors (empty if all resolved).
    """
    errors: list[SaveSimulationFieldError] = []

    async with pool.acquire() as conn:
        # ── Single-select creatables ──────────────────────────────────────

        if request.name is not None and request.name_id is None:
            result = await create_name(conn, request.name, redis)
            request.name_id = result.id

        if request.description is not None and request.description_id is None:
            result = await create_description(conn, request.description, redis)
            request.description_id = result.id

        # ── Multi-select compound creatables (merged mode) ────────────────

        if request.scenario_flags:
            created_ids = []
            for sf in request.scenario_flags:
                result = await create_scenario_flag(
                    conn, sf.scenario_id, sf.flag_id, redis
                )
                created_ids.append(result.id)
            request.scenario_flag_ids = (request.scenario_flag_ids or []) + created_ids

        if request.scenario_positions:
            created_ids = []
            for sp in request.scenario_positions:
                result = await create_scenario_position(
                    conn, sp.scenario_id, sp.value, redis
                )
                created_ids.append(result.id)
            request.scenario_position_ids = (
                request.scenario_position_ids or []
            ) + created_ids

        if request.scenario_rubrics:
            created_ids = []
            for sr in request.scenario_rubrics:
                result = await create_scenario_rubric(
                    conn, sr.scenario_id, sr.rubric_id, redis
                )
                created_ids.append(result.id)
            request.scenario_rubric_ids = (
                request.scenario_rubric_ids or []
            ) + created_ids

        if request.scenario_time_limits:
            created_ids = []
            for stl in request.scenario_time_limits:
                result = await create_scenario_time_limit(
                    conn,
                    stl.scenario_id,
                    stl.time_limit_seconds,
                    redis,
                    negative=stl.negative,
                )
                created_ids.append(result.id)
            request.scenario_time_limit_ids = (
                request.scenario_time_limit_ids or []
            ) + created_ids

    return errors


# ---------------------------------------------------------------------------
# patch_simulation_draft_impl — composable infra architecture
# ---------------------------------------------------------------------------


async def patch_simulation_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchSimulationDraftApiRequest,
) -> PatchSimulationDraftApiResponse:
    """Simulation draft using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role
      2. compute_can_draft → permission check
      3. Value resolution (creatable resources only)
      4. create_simulation_draft entry tool (append-only snapshot)
      5. Build form state (server is source of truth)
      6. refresh_simulation_drafts MV
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
            detail="You don't have permission to create or edit simulation drafts.",
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
            result = await create_simulation_draft(
                conn,
                group_id=profile.group_id,
                session_id=session_id,
                version=new_version,
                name_ids=[request.name_id] if request.name_id else None,
                description_ids=[request.description_id]
                if request.description_id
                else None,
                flag_ids=request.flag_ids,
                department_ids=request.department_ids,
                scenario_ids=request.scenario_ids,
                scenario_flag_ids=request.scenario_flag_ids,
                scenario_position_ids=request.scenario_position_ids,
                scenario_rubric_ids=request.scenario_rubric_ids,
                scenario_time_limit_ids=request.scenario_time_limit_ids,
                profile_ids=[profile.profiles_id],
            )

    # ── Step 5: Build form state (server is source of truth) ──────────

    form_state = SimulationDraftFormState(
        name_id=request.name_id,
        description_id=request.description_id,
        flag_ids=request.flag_ids or [],
        department_ids=request.department_ids or [],
        scenario_ids=request.scenario_ids or [],
        scenario_flag_ids=request.scenario_flag_ids or [],
        scenario_position_ids=request.scenario_position_ids or [],
        scenario_rubric_ids=request.scenario_rubric_ids or [],
        scenario_time_limit_ids=request.scenario_time_limit_ids or [],
    )

    # ── Step 6: Refresh MV ─────────────────────────────────────────────

    async with pool.acquire() as conn:
        await refresh_simulation_drafts(conn)

    # ── Step 7: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["simulations", "drafts"], redis=redis)

    return PatchSimulationDraftApiResponse(
        success=True,
        draft_id=result.id,
        new_version=new_version,
        message="Draft created successfully",
        form_state=form_state,
    )
