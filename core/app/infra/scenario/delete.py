"""Scenario delete logic — composable infra architecture.

Core delete function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. resolve_scenario_permissions_context — per-item exists, departments, usage
  3. compute_can_delete — permission check
  4. delete_scenarios — bulk delete tool
  5. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.delete.delete_artifact import restore_artifacts
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.infra.scenario.permissions import compute_can_delete
from app.infra.scenario.permissions_context import resolve_scenario_permissions_context
from app.infra.scenario.refresh import refresh_scenario_impl
from app.infra.scenario.types import (
    DeleteScenarioApiResponse,
    DeleteScenarioResult,
)
from app.tools.artifacts.scenario.delete import delete_scenarios
from app.tools.artifacts.scenario.get import get_scenarios
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.resources.names.get import get_names
from app.utils.cache.hedged_row import transaction_with_writeback

ARTIFACT = "scenario"


async def delete_scenario_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    ids: list[UUID] | None = None,
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    # All-matching path (additive — explicit-ids path stays untouched).
    all: bool = False,
    excluded_ids: list[UUID] | None = None,
    search: str | None = None,
    persona_ids: list[UUID] | None = None,
    simulation_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    persona_search: str | None = None,
    simulation_search: str | None = None,
    department_search: str | None = None,
    flag_search: str | None = None,
) -> DeleteScenarioApiResponse:
    """Scenario bulk delete using composable infra functions.

    Three call shapes:
      - First call (explicit): ``ids`` required.
      - First call (all-matching): ``all=true`` plus filter fields. The
        impl resolves matching ids via ``resolve_matching_scenario_ids``,
        subtracts ``excluded_ids``, then runs the existing per-row flow.
        Per-row permission failures soft-skip (returned in results)
        rather than aborting the whole call.
      - Ack call: ``idempotency_key`` + ``accept`` only — no ``ids``
        needed, the dormant deletion is located by the operation key.

    Flow (first call):
      1. (all-matching only) resolve_matching_scenario_ids → ids
      2. resolve_profile_identity_context → role
      3. Per-item: resolve_scenario_permissions_context → exists, departments, usage
      4. Per-item: compute_can_delete → permission check
         - Explicit path: fail fast (existing behavior)
         - All-matching path: soft-skip with per-row result
      5. Fetch names for result messages
      6. Single transaction: delete_scenarios → bulk delete
      7. canonical refresh
    """

    # ── Short-circuit: ack path ───────────────────────────────────────
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "delete":
            raise HTTPException(
                status_code=404,
                detail="No pending scenario delete for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            # Confirm deletion: no-op (already deactivated by soft delete)
            pass
        else:
            # Reject: restore soft-deleted artifact
            async with pool.acquire() as conn:
                async with transaction_with_writeback(conn):
                    await restore_artifacts(
                        conn,
                        table="scenario_artifact",
                        ids=[target_id],
                    )

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                redis,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation="delete",
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
        return DeleteScenarioApiResponse(
            results=[
                DeleteScenarioResult(
                    success=True,
                    scenario_id=target_id,
                    message="Delete confirmed" if accept else "Delete rejected - scenario restored",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── All-matching path: resolve ids server-side ────────────────────
    # Past the ack short-circuit and ``all=true`` ⇒ enumerate every
    # scenario matching the filter, then subtract ``excluded_ids``.
    # The per-row permission check below filters out anything the
    # user can't delete (soft-skip, returned in results).
    if all:
        from app.infra.scenario.resolve_matching_ids import resolve_matching_scenario_ids
        matching = await resolve_matching_scenario_ids(
            pool, redis,
            profile_id=profile_id,
            search=search,
            persona_ids=persona_ids,
            simulation_ids=simulation_ids,
            filter_department_ids=filter_department_ids,
            persona_search=persona_search,
            simulation_search=simulation_search,
            department_search=department_search,
            flag_search=flag_search,
        )
        excluded = set(excluded_ids or [])
        ids = [sid for sid in matching if sid not in excluded]

    # ── First-call requirements ───────────────────────────────────────
    if not ids:
        if all:
            # Empty matching set — return an empty results list rather
            # than 400. The user's intent ("delete all matching") is
            # well-formed; the universe just happens to be empty.
            return DeleteScenarioApiResponse(results=[], idempotency_key=idempotency_key)
        raise HTTPException(
            status_code=400,
            detail="`scenario_ids` is required for first-call deletion "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with filter fields).",
        )

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

    # ── Step 2+3: Per-item permission checks ──────────────────────────
    # Explicit-ids path fails fast (preserves existing 404/403 behavior).
    # All-matching path soft-skips: collects per-row results so the
    # toast can say "X deleted, Y skipped (no permission)" without
    # aborting rows the user CAN delete.
    skipped_results: list[DeleteScenarioResult] = []
    permitted_ids: list[UUID] = []

    with timed("permissions"):
     for idx, scenario_id in enumerate(ids):
        ctx = await resolve_scenario_permissions_context(pool, scenario_id)

        if not ctx.exists:
            if all:
                skipped_results.append(DeleteScenarioResult(
                    success=False, scenario_id=scenario_id,
                    message=f"Scenario {scenario_id} not found (skipped)",
                ))
                continue
            raise HTTPException(
                status_code=404,
                detail=f"Item {idx}: Scenario {scenario_id} not found.",
            )

        if not compute_can_delete(
            role_level=profile.role_level, role_permissions=profile.role_permissions,
            scenario_department_ids=ctx.department_ids,
            active_simulation_count=ctx.active_simulation_count,
            user_department_ids=profile.department_ids,
        ):
            if all:
                skipped_results.append(DeleteScenarioResult(
                    success=False, scenario_id=scenario_id,
                    message=f"No permission to delete scenario {scenario_id} (skipped)",
                ))
                continue
            raise HTTPException(
                status_code=403,
                detail=f"Item {idx}: You don't have permission to delete this scenario.",
            )

        permitted_ids.append(scenario_id)

    # All-matching path: replace ``ids`` with the filtered set. Explicit
    # path leaves it alone (it already raised on any failure).
    if all:
        ids = permitted_ids
        if not ids:
            # Every matched row was skipped — return only the skipped
            # results. No actual delete fires.
            return DeleteScenarioApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    # ── Step 4: Fetch names for result messages ───────────────────────

    name_map: dict[UUID, str] = {}
    with timed("hydrate_names"):
      async with pool.acquire() as conn:
        artifacts = await get_scenarios(conn, ids, names=True)
        for artifact in artifacts:
            name = "Unknown"
            if artifact.name_ids:
                name_resources = await get_names(pool, artifact.name_ids, redis)
                if name_resources:
                    name = name_resources[0].name or "Unknown"
            name_map[artifact.id] = name

    # ── Step 5: Single transaction — bulk delete ──────────────────────

    with timed("db_write"):
      async with pool.acquire() as conn:
        async with transaction_with_writeback(conn):
            result = await delete_scenarios(conn, ids, soft=soft)

            if soft and idempotency_key is not None:
                for sid in result.deleted_ids:
                    await create_soft_call(
                        conn,
                        redis,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="delete",
                        artifact_id=sid,
                    )

    # Refresh soft_calls_mv outside the txn.
    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    # ── Step 6: Canonical refresh ─────────────────────────────────────

    with timed("refresh"):
        await refresh_scenario_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (result.deleted_ids[0] if result.deleted_ids else None),
        )

    results = [
        DeleteScenarioResult(
            success=True,
            scenario_id=pid,
            message=(
                f"Scenario '{name_map.get(pid, 'Unknown')}' deleted (pending acceptance)"
                if soft
                else f"Scenario '{name_map.get(pid, 'Unknown')}' deleted successfully"
            ),
        )
        for pid in result.deleted_ids
    ]

    # All-matching path threads any soft-skipped rows back into the
    # response so the client can surface "X deleted, Y skipped" in
    # one go. Explicit-ids path's skipped_results is empty.
    return DeleteScenarioApiResponse(
        results=results + skipped_results,
        idempotency_key=idempotency_key,
    )
