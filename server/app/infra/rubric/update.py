"""Rubric update logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. resolve_rubric_permissions_context — per-item access + edit check
  3. resolve_rubric_values — raw value → ID resolution
  4. update_rubric_artifact — junction writes (partial update)
  5. create_denormalized_snapshot — rubrics_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.rubric.permissions_context import (
    create_denormalized_snapshot,
    resolve_rubric_permissions_context,
    resolve_rubric_values,
)
from app.tools.artifacts.rubric.update import (
    _UNSET,
)
from app.tools.artifacts.rubric.update import (
    update_rubric as update_rubric_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags


async def update_rubric_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
) -> dict:
    """Rubric bulk update using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. Per-item: resolve_rubric_permissions_context → exists + compute_can_edit
      3. Per-item value resolution (raw → ID, no required field enforcement)
      4. Single transaction: update_rubric_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
    from app.infra.rubric.permissions import compute_can_edit
    from app.infra.rubric.types import (
        RubricResultItem,
        UpdateRubricApiResponse,
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

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            perms = await resolve_rubric_permissions_context(conn, item.rubric_id)
            if not perms.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Rubric {item.rubric_id} not found.",
                )
            if not compute_can_edit(
                user_role=profile.role,
                rubric_department_ids=perms.department_ids,
                active_simulation_count=perms.active_simulation_count,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this rubric.",
                )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[RubricResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_rubric_values(
                conn, redis, item, is_create=False
            )
            if item_errors:
                has_errors = True
                error_results.append(
                    RubricResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(
                    RubricResultItem(success=True, message="Validated")
                )

    if has_errors:
        return UpdateRubricApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[RubricResultItem] = []

    for item in items:
        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
        rubrics_resource_id = await create_denormalized_snapshot(
            pool,
            redis,
            name_id=item.name_id,
            description_id=item.description_id,
            department_ids=item.department_ids,
            standard_group_ids=item.standard_group_ids,
        )

        # Artifact update inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_rubric_artifact(
                    conn,
                    item.rubric_id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id
                    if item.description_id
                    else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=[item.active_flag_id] if item.active_flag_id else None,
                    point_ids=item.point_ids,
                    standard_group_ids=item.standard_group_ids,
                    standard_ids=item.standard_ids,
                    rubric_ids=[rubrics_resource_id],
                )

        results.append(
            RubricResultItem(
                success=True,
                rubric_id=item.rubric_id,
                message="Rubric updated successfully",
            )
        )

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["rubrics"], redis=redis)

    return UpdateRubricApiResponse(results=results)
