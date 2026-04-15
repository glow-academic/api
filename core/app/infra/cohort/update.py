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
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.cohort.update import (
    _UNSET,
)
from app.tools.artifacts.cohort.update import (
    update_cohort as update_cohort_artifact,
)
from app.tools.artifacts.cohort.get import get_cohorts
from app.infra.cohort.types import UpdateCohortApiRequest, UpdateCohortApiResponse
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


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

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. Per-item: resolve_cohort_permissions_context → exists + compute_can_edit
      3. Per-item value resolution (raw → ID, no required field enforcement)
      4. Single transaction: update_cohort_artifact + denormalized snapshot per item
      5. sync_home_practice_entries (non-fatal, non-soft only)
      6. refresh_cohort_impl (non-soft only)
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
    items = request.cohorts

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
        async with pool.acquire() as conn:
            perms = await resolve_cohort_permissions_context(conn, item.cohort_id)
        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Item {idx}: Cohort {item.cohort_id} not found.",
            )
        if not has_access(profile.role_level, profile.department_ids, perms.department_ids):
            raise HTTPException(
                status_code=403,
                detail=f"Item {idx}: You don't have access to this cohort.",
            )
        if not compute_can_edit(
            role_level=profile.role_level, role_permissions=profile.role_permissions,
            cohort_department_ids=perms.department_ids,
            user_department_ids=profile.department_ids,
        ):
            raise HTTPException(
                status_code=403,
                detail=f"Item {idx}: You don't have permission to update this cohort.",
            )

    # ── Step 3: ACK short-circuit ─────────────────────────────────────

    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await update_cohort_artifact(conn, idempotency_key, soft=False)

            async with pool.acquire() as conn:
                artifacts = await get_cohorts(
                    conn,
                    [idempotency_key],
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
                    cohort_id=idempotency_key,
                    message="Update accepted" if accept else "Update rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── Step 4: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[CohortResultItem] = []

    for idx, item in enumerate(items):
        async with pool.acquire() as conn:
            item_errors = await resolve_cohort_values(
                conn, redis, item, is_create=False
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

    # ── Step 5: Single transaction ─────────────────────────────────────

    results: list[CohortResultItem] = []
    sync_items: list[tuple[UUID, object]] = []

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

        flag_ids = [item.active_flag_id] if item.active_flag_id else None

        # Artifact update inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_cohort_artifact(
                    conn,
                    item.cohort_id,
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

        results.append(
            CohortResultItem(
                success=True,
                cohort_id=item.cohort_id,
                message="Cohort updated (pending acceptance)" if soft else "Cohort updated successfully",
            )
        )
        if not soft and cohorts_resource_id is not None:
            sync_items.append((cohorts_resource_id, item))

    # ── Step 6: Sync entry rows (non-fatal, non-soft only) ────────────

    if not soft:
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

    first_id = results[0].cohort_id if results else None
    await refresh_cohort_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=idempotency_key or first_id,
    )

    return UpdateCohortApiResponse(results=results, idempotency_key=idempotency_key)
