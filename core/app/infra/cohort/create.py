"""Cohort create logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_create — permission check
  3. resolve_cohort_values — raw value → ID resolution
  4. create_cohort_artifact — junction writes
  5. create_denormalized_snapshot — cohorts_resource snapshot
  6. refresh_cohort_impl — canonical refresh
  7. sync_home_practice_entries — pre-create home/practice + chat entries
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.cohort.permissions_context import (
    create_denormalized_snapshot,
    resolve_cohort_values,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.cohort.refresh import refresh_cohort_impl
from app.tools.artifacts.cohort.create import (
    create_cohort as create_cohort_artifact,
)
from app.tools.artifacts.cohort.get import get_cohorts
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


from app.infra.cohort.types import (
    CreateCohortApiRequest,
    CreateCohortItem,
    CohortFieldError,
    CohortResultItem,
    CreateCohortApiResponse,
)


async def create_cohort_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: CreateCohortApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> CreateCohortApiResponse:
    """Cohort bulk create using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. compute_can_create — single check (applies to all items)
      3. Per-item value resolution (raw → ID, required field enforcement)
      4. Single transaction: create_cohort_artifact + denormalized snapshot per item
      5. invalidate_tags
      6. sync_home_practice_entries (non-fatal)
    """
    from app.infra.cohort.permissions import compute_can_create

    items = request.cohorts
    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key and accept is None:
        accept = request.accept

    async def _refresh_cohort(
        *,
        operation_key: UUID | None,
        session_id_value: UUID | None,
        soft_value: bool,
    ) -> None:
        _ = (operation_key, session_id_value, soft_value)
        await refresh_cohort_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id_value,
            soft=soft_value,
            operation_key=operation_key,
        )

    async def _create_items(
        cohort_items: list[CreateCohortItem],
        *,
        soft_value: bool,
        operation_key: UUID | None,
    ) -> list[CohortResultItem]:
        has_errors = False
        error_results: list[CohortResultItem] = []

        for idx, item in enumerate(cohort_items):
            async with pool.acquire() as conn:
                item_errors = await resolve_cohort_values(conn, redis, item, is_create=True)
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
            return error_results

        results: list[CohortResultItem] = []
        sync_items: list[tuple[UUID, object]] = []

        snapshot_ids: list[UUID] = []
        if not soft_value:
            for item in cohort_items:
                cohorts_resource_id = await create_denormalized_snapshot(
                    pool,
                    redis,
                    id=item.resource_id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=item.department_ids,
                    simulation_ids=item.simulation_ids,
                    profile_ids=item.profile_ids,
                    profile_persona_ids=item.profile_persona_ids,
                    simulation_position_ids=item.simulation_position_ids,
                    simulation_availability_ids=item.simulation_availability_ids,
                )
                snapshot_ids.append(cohorts_resource_id)

        for idx, item in enumerate(cohort_items):
            flag_ids = [item.active_flag_id] if item.active_flag_id else None

            async with pool.acquire() as conn:
                async with conn.transaction():
                    result = await create_cohort_artifact(
                        conn,
                        id=item.id,
                        name_id=item.name_id,
                        description_id=item.description_id,
                        department_ids=item.department_ids,
                        flag_ids=flag_ids,
                        simulation_ids=item.simulation_ids,
                        simulation_position_ids=item.simulation_position_ids,
                        simulation_availability_ids=item.simulation_availability_ids,
                        profile_ids=item.profile_ids,
                        profile_persona_ids=item.profile_persona_ids,
                        cohort_ids=[snapshot_ids[idx]] if snapshot_ids else None,
                        soft=soft_value,
                    )

            results.append(
                CohortResultItem(
                    success=True,
                    cohort_id=result.id,
                    message="Cohort created (pending acceptance)" if soft_value else "Cohort created successfully",
                )
            )
            if not soft_value:
                sync_items.append((snapshot_ids[idx], item))

        refresh_key = operation_key or (results[0].cohort_id if results else None)
        await _refresh_cohort(
            operation_key=refresh_key,
            session_id_value=session_id,
            soft_value=soft_value,
        )

        if not soft_value:
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

        return results

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

    # For create, pass department_ids from the first item (or empty)
    request_department_ids = (
        [str(d) for d in (items[0].department_ids or [])]
        if items and items[0].department_ids
        else []
    )
    if not compute_can_create(role_level=profile.role_level, role_permissions=profile.role_permissions, department_ids=request_department_ids):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create cohorts.",
        )

    # ── Step 3: ACK short-circuit ─────────────────────────────────────
    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await create_cohort_artifact(conn, id=idempotency_key, soft=False)

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

        return CreateCohortApiResponse(
            results=[
                CohortResultItem(
                    success=True,
                    cohort_id=idempotency_key,
                    message="Cohort accepted" if accept else "Cohort rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    results = await _create_items(
        items,
        soft_value=soft,
        operation_key=idempotency_key,
    )

    return CreateCohortApiResponse(results=results, idempotency_key=idempotency_key)
