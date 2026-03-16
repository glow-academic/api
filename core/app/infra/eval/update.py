"""Eval update logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. resolve_eval_permissions_context — per-item access + edit check
  3. resolve_eval_values — raw value → ID resolution
  4. update_eval_artifact — junction writes (partial update)
  5. create_denormalized_snapshot — evals_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.eval.permissions_context import (
    create_denormalized_snapshot,
    resolve_eval_permissions_context,
    resolve_eval_values,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.eval.update import (
    _UNSET,
)
from app.tools.artifacts.eval.update import (
    update_eval as update_eval_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags


async def update_eval_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
) -> dict:
    """Eval bulk update using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. Per-item: resolve_eval_permissions_context → exists + compute_can_edit
      3. Per-item value resolution (raw → ID, no required field enforcement)
      4. Single transaction: update_eval_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
    from app.infra.eval.permissions import compute_can_edit
    from app.infra.eval.types import (
        EvalResultItem,
        UpdateEvalApiResponse,
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
            perms = await resolve_eval_permissions_context(conn, item.eval_id)
            if not perms.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Eval {item.eval_id} not found.",
                )
            if not compute_can_edit(
                user_role=profile.role,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this eval.",
                )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[EvalResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_eval_values(conn, redis, item, is_create=False)
            if item_errors:
                has_errors = True
                error_results.append(
                    EvalResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(EvalResultItem(success=True, message="Validated"))

    if has_errors:
        return UpdateEvalApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[EvalResultItem] = []

    for item in items:
        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
        evals_resource_id = await create_denormalized_snapshot(
            pool,
            redis,
            name_id=item.name_id,
            description_id=item.description_id,
            department_ids=item.department_ids,
            model_ids=item.model_ids,
            model_rubric_ids=item.model_rubric_ids,
            model_flag_ids=item.model_flag_ids,
            model_position_ids=item.model_position_ids,
        )

        # Artifact update inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_eval_artifact(
                    conn,
                    item.eval_id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id
                    if item.description_id
                    else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=item.flag_ids,
                    model_ids=item.model_ids,
                    model_flag_ids=item.model_flag_ids,
                    model_rubric_ids=item.model_rubric_ids,
                    model_position_ids=item.model_position_ids,
                    eval_ids=[evals_resource_id],
                )

        results.append(
            EvalResultItem(
                success=True,
                eval_id=item.eval_id,
                message="Eval updated successfully",
            )
        )

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["evals"], redis=redis)

    return UpdateEvalApiResponse(results=results)
