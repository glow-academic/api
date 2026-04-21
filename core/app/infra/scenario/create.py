"""Scenario create logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_create — permission check
  3. resolve_scenario_values — raw value → ID resolution
  4. create_scenario_artifact — junction writes
  5. create_denormalized_snapshot — scenarios_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.scenario.permissions_context import (
    create_denormalized_snapshot,
    resolve_scenario_values,
)
from app.infra.scenario.refresh import refresh_scenario_impl
from app.tools.artifacts.scenario.create import (
    create_scenario as create_scenario_artifact,
)
from app.tools.artifacts.scenario.get import get_scenarios

from app.infra.scenario.types import (
    CreateScenarioApiRequest,
    CreateScenarioItem,
    ScenarioResultItem,
    CreateScenarioApiResponse,
)


def _batch_department_scope(items: list[CreateScenarioItem]) -> list[str] | None:
    """Summarize whether every item is department-scoped for create permissions."""
    if not items:
        return None

    for item in items:
        if not (item.department_ids or item.departments):
            return None

    return ["department-scoped"]


def _collect_flag_ids(item: CreateScenarioItem) -> list[UUID] | None:
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


async def create_scenario_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: CreateScenarioApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> CreateScenarioApiResponse:
    """Scenario bulk create using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. compute_can_create — single check (applies to all items)
      3. Per-item value resolution (raw → ID, required field enforcement)
      4. Single transaction: create_scenario_artifact + denormalized snapshot per item
      5. Refresh via canonical scenario refresh
    """
    from app.infra.scenario.permissions import compute_can_create

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key and accept is None:
        accept = request.accept

    items = request.scenarios

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

    if not compute_can_create(
        role_level=profile.role_level, role_permissions=profile.role_permissions,
        department_ids=_batch_department_scope(items),
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create scenarios.",
        )

    # ── Short-circuit: ack path ───────────────────────────────────────

    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await create_scenario_artifact(
                        conn,
                        id=idempotency_key,
                        soft=False,
                    )

            async with pool.acquire() as conn:
                artifacts = await get_scenarios(
                    conn,
                    [idempotency_key],
                    names=True,
                    descriptions=True,
                    departments=True,
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
            if artifacts:
                artifact = artifacts[0]
                await create_denormalized_snapshot(
                    pool,
                    redis,
                    name_id=artifact.name_ids[0] if artifact.name_ids else None,
                    description_id=artifact.description_ids[0] if artifact.description_ids else None,
                    department_ids=artifact.department_ids or None,
                    persona_ids=artifact.persona_ids or None,
                    parameter_field_ids=artifact.parameter_field_ids or None,
                    document_ids=artifact.document_ids or None,
                    objective_ids=artifact.objective_ids or None,
                    image_ids=artifact.image_ids or None,
                    video_ids=artifact.video_ids or None,
                    question_ids=artifact.question_ids or None,
                    option_ids=artifact.option_ids or None,
                    problem_statement_ids=artifact.problem_statement_ids or None,
                )

            await refresh_scenario_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                operation_key=idempotency_key,
            )

        return CreateScenarioApiResponse(
            results=[
                ScenarioResultItem(
                    success=True,
                    scenario_id=idempotency_key,
                    message="Scenario accepted" if accept else "Scenario rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    response = await _create_scenarios(
        pool,
        redis,
        profile_id=profile_id,
        items=items,
        soft=soft,
        session_id=session_id,
        operation_key=idempotency_key,
    )

    return CreateScenarioApiResponse(
        results=response.results,
        idempotency_key=idempotency_key,
    )


async def _create_scenarios(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list[CreateScenarioItem],
    soft: bool,
    session_id: UUID | None,
    operation_key: UUID | None,
) -> CreateScenarioApiResponse:
    """Shared scenario create flow for normal and ack-promote paths."""
    has_errors = False
    error_results: list[ScenarioResultItem] = []

    for idx, item in enumerate(items):
        item_errors = await resolve_scenario_values(pool, redis, item, is_create=True)
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
        return CreateScenarioApiResponse(results=error_results)

    # ── Step 4: Denormalized snapshots (skip when soft — dormant artifact) ─

    snapshot_ids: list[UUID] = []
    if not soft:
        for item in items:
            scenarios_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                id=item.resource_id,
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
                images_enabled=item.images_enabled_flag,
                objectives_enabled=item.objectives_enabled_flag,
                problem_statement_enabled=item.problem_statement_enabled_flag,
                questions_enabled=item.questions_enabled_flag,
                video_enabled=item.video_enabled_flag,
            )
            snapshot_ids.append(scenarios_resource_id)

    # ── Step 5: Single transaction — artifact writes ───────────────────

    results: list[ScenarioResultItem] = []

    async with pool.acquire() as conn:
        async with conn.transaction():
            for idx, item in enumerate(items):
                flag_ids = _collect_flag_ids(item)

                result = await create_scenario_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
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
                    scenario_ids=[snapshot_ids[idx]] if snapshot_ids else None,
                    soft=soft,
                )

                results.append(
                    ScenarioResultItem(
                        success=True,
                        scenario_id=result.id,
                        message="Scenario created (pending acceptance)"
                        if soft
                        else "Scenario created successfully",
                    )
                )

    # ── Step 6: Refresh via canonical scenario refresh ─────────────────

    first_id = results[0].scenario_id if results else None
    await refresh_scenario_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=operation_key or first_id,
    )

    return CreateScenarioApiResponse(results=results)
