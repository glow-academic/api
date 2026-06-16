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
from app.infra.server_timing import timed
from app.infra.scenario.permissions_context import (
    create_denormalized_snapshot,
    resolve_scenario_permissions_context,
    resolve_scenario_values,
)
from app.infra.scenario.refresh import refresh_scenario_impl
from app.infra.scenario.types import (
    ListScenarioApiScenario,
    UpdateScenarioApiRequest,
    UpdateScenarioApiResponse,
)
from app.tools.artifacts.scenario.get import get_scenarios
from app.tools.artifacts.scenario.update import (
    _UNSET,
)
from app.tools.artifacts.scenario.update import (
    update_scenario as update_scenario_artifact,
)
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.utils.cache.hedged_row import transaction_with_writeback

ARTIFACT = "scenario"

if TYPE_CHECKING:
    from app.infra.scenario.types import UpdateScenarioItem


def _collect_flag_ids(item: "UpdateScenarioItem") -> list[UUID] | None:
    """Return the canonical flag_ids list (or None if empty)."""
    flag_ids: list[UUID] = list(item.flag_ids or [])
    return flag_ids if flag_ids else None


async def update_scenario_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdateScenarioApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdateScenarioApiResponse:
    """Scenario bulk update using composable infra functions.

    Three call shapes:
      - First call (explicit): ``request.scenarios`` required.
      - First call (all-matching): ``request.all=true`` plus ``patch``
        plus filter fields. The impl resolves matching ids, clones
        the patch per id (stamping each id), then runs the existing
        per-row update flow. Per-row permission failures soft-skip.
      - Ack call: ``idempotency_key`` + ``accept`` only.

    Flow (first call):
      1. (all-matching only) resolve_matching_scenario_ids → synth items
      2. resolve_profile_identity_context → role, department_ids
      3. Per-item: resolve_scenario_permissions_context → exists + compute_can_edit
      4. Per-item value resolution (raw → ID, no required field enforcement)
      5. Single transaction: update_scenario_artifact + denormalized snapshot per item
      6. canonical refresh via refresh_scenario_impl
    """
    from app.infra.scenario.permissions import compute_can_edit
    from app.infra.scenario.types import (
        ScenarioResultItem,
    )

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key and accept is None:
        accept = request.accept

    # ── Short-circuit: ack path ───────────────────────────────────────
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "update":
            raise HTTPException(
                status_code=404,
                detail="No pending scenario update for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                async with transaction_with_writeback(conn):
                    await update_scenario_artifact(
                        conn,
                        target_id,
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
                operation="update",
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

        return UpdateScenarioApiResponse(
            results=[
                ScenarioResultItem(
                    success=True,
                    scenario_id=target_id,
                    message="Update accepted" if accept else "Update rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── All-matching path: resolve ids + synthesize per-row items ─────
    # Past the ack short-circuit and ``all=true`` ⇒ enumerate every
    # scenario matching the filter, then clone ``request.patch`` per
    # id (stamping the resolved id). The downstream per-row flow runs
    # unchanged. Per-row permission failures soft-skip (collected into
    # ``skipped_results`` and threaded into the final response).
    skipped_results: list[ScenarioResultItem] = []

    if request.all:
        if request.patch is None:
            raise HTTPException(
                status_code=400,
                detail="`patch` is required when `all=true` "
                "(it carries the shared change set applied to every matched row).",
            )
        from app.infra.scenario.resolve_matching_ids import resolve_matching_scenario_ids
        from app.infra.scenario.types import UpdateScenarioItem

        matching = await resolve_matching_scenario_ids(
            pool, redis,
            profile_id=profile_id,
            search=request.search,
            persona_ids=request.persona_ids,
            simulation_ids=request.simulation_ids,
            filter_department_ids=request.filter_department_ids,
            persona_search=request.persona_search,
            simulation_search=request.simulation_search,
            department_search=request.department_search,
            flag_search=request.flag_search,
        )
        excluded = set(request.excluded_ids or [])
        resolved_ids = [sid for sid in matching if sid not in excluded]

        if not resolved_ids:
            # Empty matching set — well-formed intent, just no rows.
            return UpdateScenarioApiResponse(results=[], idempotency_key=idempotency_key)

        # Clone the patch per matched row, stamping the resolved id.
        # ``model_dump(exclude_unset=True, exclude={"id"})`` keeps sparse
        # semantics — only fields the client actually set are written.
        patch_fields = request.patch.model_dump(exclude_unset=True, exclude={"id"})
        synth_items = [UpdateScenarioItem(id=sid, **patch_fields) for sid in resolved_ids]
        # Splice into the request shape downstream code expects.
        request = request.model_copy(update={"scenarios": synth_items})

    # ── First-call requirements ───────────────────────────────────────
    if not request.scenarios:
        raise HTTPException(
            status_code=400,
            detail="`request.scenarios` is required for first-call update "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with `patch` and filter fields).",
        )

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

    # ── Step 2: Per-item permission check ──────────────────────────────
    # Explicit path fails fast (existing behavior).
    # All-matching path soft-skips so the response carries per-row
    # outcomes without aborting rows the user CAN edit.
    is_all_matching = bool(request.all)
    permitted_items: list = []

    with timed("permissions"):
     for idx, item in enumerate(items):
        perms = await resolve_scenario_permissions_context(pool, item.id)
        if not perms.exists:
            if is_all_matching:
                skipped_results.append(ScenarioResultItem(
                    success=False, scenario_id=item.id,
                    message=f"Scenario {item.id} not found (skipped)",
                ))
                continue
            raise HTTPException(
                status_code=404,
                detail=f"Item {idx}: Scenario {item.id} not found.",
            )
        if not compute_can_edit(
            role_level=profile.role_level, role_permissions=profile.role_permissions,
            scenario_department_ids=perms.department_ids,
            active_simulation_count=perms.active_simulation_count,
            user_department_ids=profile.department_ids,
        ):
            if is_all_matching:
                skipped_results.append(ScenarioResultItem(
                    success=False, scenario_id=item.id,
                    message=f"No permission to update scenario {item.id} (skipped)",
                ))
                continue
            raise HTTPException(
                status_code=403,
                detail=f"Item {idx}: You don't have permission to update this scenario.",
            )

        permitted_items.append(item)

    if is_all_matching:
        items = permitted_items
        if not items:
            return UpdateScenarioApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[ScenarioResultItem] = []

    from app.infra.scenario.permissions import compute_can_assign_departments

    with timed("resolve_values"):
     for idx, item in enumerate(items):
        item_errors = await resolve_scenario_values(pool, redis, item, is_create=False)
        # Reject cross-department reassignment: a non-top-level actor who can edit a
        # scenario in their own department must not move/retag it into a department
        # they don't belong to via body `department_ids`. compute_can_edit only scopes
        # the scenario's *existing* departments, not the target set being written.
        if item.department_ids is not None and not compute_can_assign_departments(
            role_level=profile.role_level,
            target_department_ids=item.department_ids,
            user_department_ids=profile.department_ids,
        ):
            raise HTTPException(
                status_code=403,
                detail=f"Item {idx}: You can only assign scenarios to your own departments.",
            )
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
        return UpdateScenarioApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[ScenarioResultItem] = []

    with timed("db_write"):
     for item in items:
        scenarios_resource_id = None
        if not soft:
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
            async with transaction_with_writeback(conn):
                await update_scenario_artifact(
                    conn,
                    item.id,
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
                    scenario_ids=[scenarios_resource_id] if scenarios_resource_id else None,
                    soft=soft,
                )

                # Pending ledger row tied to this tool call (see persona/update.py).
                if soft and idempotency_key is not None:
                    await create_soft_call(
                        conn,
                        redis,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="update",
                        artifact_id=item.id,
                    )

        results.append(
            ScenarioResultItem(
                success=True,
                scenario_id=item.id,
                message=(
                    "Scenario updated (pending acceptance)"
                    if soft
                    else "Scenario updated successfully"
                ),
            )
        )

    # ── Step 5: Refresh soft_calls_mv after pending ledger row insert ──

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    # ── Step 6: Canonical refresh ──────────────────────────────────────

    first_id = results[0].scenario_id if results else None
    with timed("refresh"):
        await refresh_scenario_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or first_id,
        )

    # Hydrate full row content for the client ghost rail (skip when soft).
    scenarios: list[ListScenarioApiScenario] | None = None
    if not soft:
        with timed("hydrate"):
            from app.infra.scenario.hydrate_list_rows import hydrate_scenario_list_rows
            updated_ids = [r.scenario_id for r in results if r.success and r.scenario_id is not None]
            if updated_ids:
                scenarios = await hydrate_scenario_list_rows(
                    pool, redis, profile_id=profile_id, scenario_ids=updated_ids,
                )

    # All-matching path threads soft-skipped rows back into the
    # response so the client can surface "X updated, Y skipped" in
    # one toast. Explicit path's ``skipped_results`` is empty.
    return UpdateScenarioApiResponse(
        results=results + skipped_results,
        idempotency_key=idempotency_key,
        scenarios=scenarios,
    )
