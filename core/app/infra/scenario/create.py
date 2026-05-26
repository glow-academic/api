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
from app.infra.server_timing import timed
from app.infra.scenario.permissions_context import (
    create_denormalized_snapshot,
    resolve_scenario_values,
)
from app.infra.scenario.refresh import refresh_scenario_impl
from app.infra.scenario.types import (
    CreateScenarioApiRequest,
    CreateScenarioApiResponse,
    CreateScenarioItem,
    ListScenarioApiScenario,
    ScenarioResultItem,
)
from app.tools.artifacts.scenario.create import (
    create_scenario as create_scenario_artifact,
)
from app.tools.artifacts.scenario.get import get_scenarios
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls

ARTIFACT = "scenario"


def _batch_department_scope(items: list[CreateScenarioItem]) -> list[str] | None:
    """Summarize whether every item is department-scoped for create permissions."""
    if not items:
        return None

    for item in items:
        if not (item.department_ids or item.departments):
            return None

    return ["department-scoped"]


def _collect_flag_ids(item: CreateScenarioItem) -> list[UUID] | None:
    """Return the canonical flag_ids list (or None if empty)."""
    flag_ids = list(item.flag_ids or [])
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

    with timed("profile"):
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

    with timed("permissions"):
        if not compute_can_create(
            role_level=profile.role_level, role_permissions=profile.role_permissions,
            department_ids=_batch_department_scope(items),
        ):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to create scenarios.",
            )

    # ── Short-circuit: ack path ───────────────────────────────────────
    # ``idempotency_key`` is the originating tool call's ``calls_entry.id``.
    # The ``soft_calls_mv`` ledger holds (artifact, operation, artifact_id)
    # we need to act on. See project_soft_calls_entry_pattern.

    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "create":
            raise HTTPException(
                status_code=404,
                detail="No pending scenario create for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await create_scenario_artifact(
                        conn,
                        id=target_id,
                        soft=False,
                    )

            async with pool.acquire() as conn:
                artifacts = await get_scenarios(
                    conn,
                    [target_id],
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

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                redis,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation="create",
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
            operation_key=idempotency_key,
        )

        return CreateScenarioApiResponse(
            results=[
                ScenarioResultItem(
                    success=True,
                    scenario_id=target_id,
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

    with timed("resolve_values"):
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
      with timed("snapshot"):
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
            )
            snapshot_ids.append(scenarios_resource_id)

    # ── Step 5: Single transaction — artifact writes ───────────────────

    results: list[ScenarioResultItem] = []

    with timed("db_write"):
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

                # Soft writes append a pending ledger row tied to the
                # originating tool call so ack lookups can resolve
                # (artifact, operation, artifact_id).
                if soft and operation_key is not None:
                    await create_soft_call(
                        conn,
                        redis,
                        call_id=operation_key,
                        artifact=ARTIFACT,
                        operation="create",
                        artifact_id=result.id,
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

    # ── Step 6: Refresh soft_calls_mv after pending ledger row insert ──

    if soft and operation_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    # ── Step 7: Refresh via canonical scenario refresh ─────────────────

    first_id = results[0].scenario_id if results else None
    with timed("refresh"):
        await refresh_scenario_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=operation_key or first_id,
        )

    # Hydrate full row content for the client ghost rail (skip when soft).
    scenarios: list[ListScenarioApiScenario] | None = None
    if not soft:
        with timed("hydrate"):
            from app.infra.scenario.hydrate_list_rows import hydrate_scenario_list_rows
            new_ids = [r.scenario_id for r in results if r.success and r.scenario_id is not None]
            if new_ids:
                scenarios = await hydrate_scenario_list_rows(
                    pool, redis, profile_id=profile_id, scenario_ids=new_ids,
                )

    return CreateScenarioApiResponse(results=results, scenarios=scenarios)
