"""Cohort update logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. resolve_cohort_permissions_context — per-item access + edit check
  3. resolve_cohort_values — raw value → ID resolution
  4. update_cohort_artifact — junction writes (partial update)
  5. create_denormalized_snapshot — cohorts_resource snapshot
  6. sync_home_practice_entries — pre-create home/practice + chat entries
  7. refresh_cohort_impl — canonical cache invalidation path
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.cohort.permissions_context import (
    create_denormalized_snapshot,
    resolve_cohort_permissions_context,
    resolve_cohort_values,
)
from app.infra.cohort.refresh import refresh_cohort_impl
from app.infra.cohort.types import UpdateCohortApiRequest, UpdateCohortApiResponse
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.artifacts.cohort.get import get_cohorts
from app.tools.artifacts.cohort.update import (
    _UNSET,
)
from app.tools.artifacts.cohort.update import (
    update_cohort as update_cohort_artifact,
)
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

ARTIFACT = "cohort"


async def update_cohort_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdateCohortApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdateCohortApiResponse:
    """Cohort bulk update using composable infra functions.

    Three call shapes:
      - First call (explicit): ``request.cohorts`` required.
      - First call (all-matching): ``request.all=true`` plus ``patch``
        plus filter fields. The impl resolves matching ids, clones
        the patch per id (stamping each id), then runs the existing
        per-row update flow. Per-row permission failures soft-skip.
      - Ack call: ``idempotency_key`` + ``accept`` only.

    Flow (first call):
      1. (all-matching only) resolve_matching_cohort_ids → synth items
      2. resolve_profile_identity_context → role, department_ids
      3. Per-item: resolve_cohort_permissions_context → exists + compute_can_edit
      4. Per-item value resolution (raw → ID, no required field enforcement)
      5. Single transaction: update_cohort_artifact + denormalized snapshot per item
      6. sync_home_practice_entries (non-fatal, non-soft only)
      7. refresh_cohort_impl
    """
    from app.infra.cohort.permissions import (
        compute_can_edit,
        has_access,
    )
    from app.infra.cohort.types import (
        CohortResultItem,
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
                detail="No pending cohort update for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await update_cohort_artifact(conn, target_id, soft=False)

            async with pool.acquire() as conn:
                artifacts = await get_cohorts(
                    conn,
                    [target_id],
                    names=True,
                    descriptions=True,
                    departments=True,
                    profiles=True,
                    profile_personas=True,
                    simulations=True,
                    simulation_positions=True,
                    simulation_availability=True,
                )

            if artifacts:
                artifact = artifacts[0]
                await create_denormalized_snapshot(
                    pool,
                    redis,
                    name_id=artifact.name_ids[0] if artifact.name_ids else None,
                    description_id=artifact.description_ids[0] if artifact.description_ids else None,
                    department_ids=artifact.department_ids or None,
                    simulation_ids=artifact.simulation_ids or None,
                    profile_ids=artifact.profiles_ids or None,
                    profile_persona_ids=artifact.profile_persona_ids or None,
                    simulation_position_ids=artifact.simulation_position_ids or None,
                    simulation_availability_ids=artifact.simulation_availability_ids or None,
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

        await refresh_cohort_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )

        return UpdateCohortApiResponse(
            results=[
                CohortResultItem(
                    success=True,
                    cohort_id=target_id,
                    message="Update accepted" if accept else "Update rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── All-matching path: resolve ids + synthesize per-row items ─────
    # Past the ack short-circuit and ``all=true`` ⇒ enumerate every
    # cohort matching the filter, then clone ``request.patch`` per
    # id (stamping the resolved id). The downstream per-row flow runs
    # unchanged. Per-row permission failures soft-skip (collected into
    # ``skipped_results`` and threaded into the final response).
    skipped_results: list[CohortResultItem] = []

    if request.all:
        if request.patch is None:
            raise HTTPException(
                status_code=400,
                detail="`patch` is required when `all=true` "
                "(it carries the shared change set applied to every matched row).",
            )
        from app.infra.cohort.resolve_matching_ids import resolve_matching_cohort_ids
        from app.infra.cohort.types import UpdateCohortItem

        matching = await resolve_matching_cohort_ids(
            pool, redis,
            profile_id=profile_id,
            search=request.search,
            filter_profile_ids=request.filter_profile_ids,
            filter_simulation_ids=request.filter_simulation_ids,
            filter_department_ids=request.filter_department_ids,
            profile_search=request.profile_search,
            simulation_search=request.simulation_search,
            department_search=request.department_search,
            flag_search=request.flag_search,
        )
        excluded = set(request.excluded_ids or [])
        resolved_ids = [cid for cid in matching if cid not in excluded]

        if not resolved_ids:
            # Empty matching set — well-formed intent, just no rows.
            return UpdateCohortApiResponse(results=[], idempotency_key=idempotency_key)

        # Clone the patch per matched row, stamping the resolved id.
        # ``model_dump(exclude_unset=True, exclude={"id"})`` keeps sparse
        # semantics — only fields the client actually set are written.
        patch_fields = request.patch.model_dump(exclude_unset=True, exclude={"id"})
        synth_items = [UpdateCohortItem(id=cid, **patch_fields) for cid in resolved_ids]
        # Splice into the request shape downstream code expects.
        request = request.model_copy(update={"cohorts": synth_items})

    # ── First-call requirements ───────────────────────────────────────
    if not request.cohorts:
        raise HTTPException(
            status_code=400,
            detail="`request.cohorts` is required for first-call update "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with `patch` and filter fields).",
        )

    items = request.cohorts

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
        async with pool.acquire() as conn:
            perms = await resolve_cohort_permissions_context(conn, item.id)
        if not perms.exists:
            if is_all_matching:
                skipped_results.append(CohortResultItem(
                    success=False, cohort_id=item.id,
                    message=f"Cohort {item.id} not found (skipped)",
                ))
                continue
            raise HTTPException(
                status_code=404,
                detail=f"Item {idx}: Cohort {item.id} not found.",
            )
        if not has_access(profile.role_level, profile.department_ids, perms.department_ids):
            if is_all_matching:
                skipped_results.append(CohortResultItem(
                    success=False, cohort_id=item.id,
                    message=f"No access to cohort {item.id} (skipped)",
                ))
                continue
            raise HTTPException(
                status_code=403,
                detail=f"Item {idx}: You don't have access to this cohort.",
            )
        if not compute_can_edit(
            role_level=profile.role_level, role_permissions=profile.role_permissions,
            cohort_department_ids=perms.department_ids,
            user_department_ids=profile.department_ids,
        ):
            if is_all_matching:
                skipped_results.append(CohortResultItem(
                    success=False, cohort_id=item.id,
                    message=f"No permission to update cohort {item.id} (skipped)",
                ))
                continue
            raise HTTPException(
                status_code=403,
                detail=f"Item {idx}: You don't have permission to update this cohort.",
            )

        permitted_items.append(item)

    if is_all_matching:
        items = permitted_items
        if not items:
            return UpdateCohortApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[CohortResultItem] = []

    from app.infra.cohort.permissions import compute_can_assign_departments

    with timed("resolve_values"):
     for idx, item in enumerate(items):
        async with pool.acquire() as conn:
            item_errors = await resolve_cohort_values(
                conn, redis, item, is_create=False
            )
        # Reject cross-department reassignment: a non-top-level actor who can edit a
        # cohort in their own department must not move/retag it into a department they
        # don't belong to via body `department_ids`. compute_can_edit only scopes the
        # cohort's *existing* departments, not the target set being written.
        if item.department_ids is not None and not compute_can_assign_departments(
            role_level=profile.role_level,
            target_department_ids=item.department_ids,
            user_department_ids=profile.department_ids,
        ):
            raise HTTPException(
                status_code=403,
                detail=f"Item {idx}: You can only assign cohorts to your own departments.",
            )
        if item_errors:
            has_errors = True
            error_results.append(
                CohortResultItem(
                    success=False,
                    message=f"Item {idx}: Validation errors",
                    errors=item_errors,
                )
            )
        else:
            error_results.append(CohortResultItem(success=True, message="Validated"))

    if has_errors:
        return UpdateCohortApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[CohortResultItem] = []
    sync_items: list[tuple[UUID, object]] = []

    with timed("db_write"):
     for item in items:
        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
        cohorts_resource_id = None
        if not soft:
            cohorts_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                simulation_ids=item.simulation_ids,
                profile_ids=item.profile_ids,
                profile_persona_ids=item.profile_persona_ids,
                simulation_position_ids=item.simulation_position_ids,
                simulation_availability_ids=item.simulation_availability_ids,
            )

        flag_ids = list(item.flag_ids) if item.flag_ids else None

        # Artifact update inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_cohort_artifact(
                    conn,
                    item.id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id
                    if item.description_id
                    else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=flag_ids,
                    simulation_ids=item.simulation_ids,
                    simulation_position_ids=item.simulation_position_ids,
                    simulation_availability_ids=item.simulation_availability_ids,
                    profile_ids=item.profile_ids,
                    profile_persona_ids=item.profile_persona_ids,
                    cohort_ids=[cohorts_resource_id] if cohorts_resource_id is not None else None,
                    soft=soft,
                )

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
            CohortResultItem(
                success=True,
                cohort_id=item.id,
                message="Cohort updated (pending acceptance)" if soft else "Cohort updated successfully",
            )
        )
        if not soft and cohorts_resource_id is not None:
            sync_items.append((cohorts_resource_id, item))

    # ── Step 5: Sync entry rows (non-fatal, non-soft only) ────────────

    if not soft:
      with timed("home_practice_sync"):
        for resource_id, item in sync_items:
            try:
                from app.infra.home_practice_sync import sync_home_practice_entries

                await sync_home_practice_entries(
                    pool=pool,
                    cohorts_resource_id=resource_id,
                    simulation_ids=item.simulation_ids or [],
                    simulation_position_ids=item.simulation_position_ids or [],
                    simulation_availability_ids=item.simulation_availability_ids or [],
                    department_ids=item.department_ids or [],
                    profile_ids=item.profile_ids or [],
                    profile_persona_ids=item.profile_persona_ids or [],
                )
            except Exception as sync_err:
                logger.warning(
                    f"sync_home_practice_entries failed (non-fatal): {sync_err}"
                )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    first_id = results[0].cohort_id if results else None
    with timed("refresh"):
        await refresh_cohort_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or first_id,
        )

    # All-matching path threads soft-skipped rows back into the
    # response so the client can surface "X updated, Y skipped" in
    # one toast. Explicit path's ``skipped_results`` is empty.
    return UpdateCohortApiResponse(
        results=results + skipped_results,
        idempotency_key=idempotency_key,
    )
