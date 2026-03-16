"""Cohort update logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. resolve_cohort_permissions_context — per-item access + edit check
  3. resolve_cohort_values — raw value → ID resolution
  4. update_cohort_artifact — junction writes (partial update)
  5. create_denormalized_snapshot — cohorts_resource snapshot
  6. sync_home_practice_entries — pre-create home/practice + chat entries
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
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.cohort.update import (
    _UNSET,
)
from app.tools.artifacts.cohort.update import (
    update_cohort as update_cohort_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def update_cohort_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
) -> dict:
    """Cohort bulk update using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. Per-item: resolve_cohort_permissions_context → exists + compute_can_edit
      3. Per-item value resolution (raw → ID, no required field enforcement)
      4. Single transaction: update_cohort_artifact + denormalized snapshot per item
      5. invalidate_tags
      6. sync_home_practice_entries (non-fatal)
    """
    from app.infra.cohort.permissions import (
        compute_can_edit,
        has_access,
    )
    from app.infra.cohort.types import (
        CohortResultItem,
        UpdateCohortApiResponse,
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
        async with pool.acquire() as conn:
            perms = await resolve_cohort_permissions_context(conn, item.cohort_id)
        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Item {idx}: Cohort {item.cohort_id} not found.",
            )
        if not has_access(profile.role, profile.department_ids, perms.department_ids):
            raise HTTPException(
                status_code=403,
                detail=f"Item {idx}: You don't have access to this cohort.",
            )
        if not compute_can_edit(
            user_role=profile.role,
            cohort_department_ids=perms.department_ids,
            user_department_ids=profile.department_ids,
        ):
            raise HTTPException(
                status_code=403,
                detail=f"Item {idx}: You don't have permission to update this cohort.",
            )

    # ── Step 3: Per-item value resolution ──────────────────────────────

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
        return UpdateCohortApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[CohortResultItem] = []
    sync_items: list[tuple[UUID, object]] = []

    for item in items:
        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
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

        flag_ids = [item.flag_id] if item.flag_id else None

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
                    cohort_ids=[cohorts_resource_id],
                )

        results.append(
            CohortResultItem(
                success=True,
                cohort_id=item.cohort_id,
                message="Cohort updated successfully",
            )
        )
        sync_items.append((cohorts_resource_id, item))

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["cohorts"], redis=redis)

    # ── Step 6: Sync entry rows (non-fatal) ────────────────────────────

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
            logger.warning(f"sync_home_practice_entries failed (non-fatal): {sync_err}")

    return UpdateCohortApiResponse(results=results)
