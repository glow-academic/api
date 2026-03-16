"""Scenario update logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. resolve_scenario_permissions_context — per-item access + edit check
  3. resolve_scenario_values — raw value → ID resolution
  4. update_scenario_artifact — junction writes (partial update)
  5. create_denormalized_snapshot — scenarios_resource snapshot
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.scenario.permissions_context import (
    create_denormalized_snapshot,
    resolve_scenario_permissions_context,
    resolve_scenario_values,
)
from app.tools.artifacts.scenario.update import (
    _UNSET,
)
from app.tools.artifacts.scenario.update import (
    update_scenario as update_scenario_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags

if TYPE_CHECKING:
    from app.infra.scenario.types import UpdateScenarioItem


def _collect_flag_ids(item: UpdateScenarioItem) -> list[UUID] | None:
    """Collect all non-None flag IDs from the item into a single list."""
    flag_ids = []
    for fid in [
        item.active_flag_id,
        item.objectives_enabled_flag_id,
        item.images_enabled_flag_id,
        item.video_enabled_flag_id,
        item.questions_enabled_flag_id,
        item.problem_statement_enabled_flag_id,
    ]:
        if fid is not None:
            flag_ids.append(fid)
    return flag_ids if flag_ids else None


async def update_scenario_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
) -> dict:
    """Scenario bulk update using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. Per-item: resolve_scenario_permissions_context → exists + compute_can_edit
      3. Per-item value resolution (raw → ID, no required field enforcement)
      4. Single transaction: update_scenario_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
    from app.infra.scenario.permissions import compute_can_edit
    from app.infra.scenario.types import (
        ScenarioResultItem,
        UpdateScenarioApiResponse,
    )

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(
        pool,
        profile_id,
        redis,
        session_id=session_id,
        draft_id=draft_id,
    )

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Per-item permission check ──────────────────────────────

    for idx, item in enumerate(items):
        perms = await resolve_scenario_permissions_context(pool, item.scenario_id)
        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Item {idx}: Scenario {item.scenario_id} not found.",
            )
        if not compute_can_edit(
            user_role=profile.role,
            scenario_department_ids=perms.department_ids,
            active_simulation_count=perms.active_simulation_count,
            user_department_ids=profile.department_ids,
        ):
            raise HTTPException(
                status_code=403,
                detail=f"Item {idx}: You don't have permission to update this scenario.",
            )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[ScenarioResultItem] = []

    for idx, item in enumerate(items):
        item_errors = await resolve_scenario_values(pool, redis, item, is_create=False)
        if item_errors:
            has_errors = True
            error_results.append(
                ScenarioResultItem(
                    success=False,
                    message=f"Item {idx}: Validation errors",
                    errors=item_errors,
                )
            )
        else:
            error_results.append(ScenarioResultItem(success=True, message="Validated"))

    if has_errors:
        return UpdateScenarioApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[ScenarioResultItem] = []

    for item in items:
        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
        scenarios_resource_id = await create_denormalized_snapshot(
            pool,
            redis,
            name_id=item.name_id,
            description_id=item.description_id,
            department_ids=item.department_ids,
            persona_ids=item.persona_ids,
            parameter_field_ids=item.parameter_field_ids,
            document_ids=item.document_ids,
            objective_ids=item.objective_ids,
            image_ids=item.image_ids,
            video_ids=item.video_ids,
            question_ids=item.question_ids,
            option_ids=item.option_ids,
            problem_statement_ids=[item.problem_statement_id]
            if item.problem_statement_id
            else None,
        )

        flag_ids = _collect_flag_ids(item)

        # Artifact update inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_scenario_artifact(
                    conn,
                    item.scenario_id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id
                    if item.description_id
                    else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=flag_ids,
                    document_ids=item.document_ids,
                    image_ids=item.image_ids,
                    objective_ids=item.objective_ids,
                    option_ids=item.option_ids,
                    parameter_field_ids=item.parameter_field_ids,
                    persona_ids=item.persona_ids,
                    problem_statement_ids=[item.problem_statement_id]
                    if item.problem_statement_id
                    else None,
                    question_ids=item.question_ids,
                    video_ids=item.video_ids,
                    scenario_ids=[scenarios_resource_id],
                )

        results.append(
            ScenarioResultItem(
                success=True,
                scenario_id=item.scenario_id,
                message="Scenario updated successfully",
            )
        )

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["scenarios"], redis=redis)

    return UpdateScenarioApiResponse(results=results)
