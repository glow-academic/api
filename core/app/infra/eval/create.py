"""Eval create logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_create — permission check
  3. resolve_eval_values — raw value → ID resolution
  4. create_eval_artifact — junction writes
  5. create_denormalized_snapshot — evals_resource snapshot
  6. sync_benchmark_entries — pre-create benchmark + invocation entries (non-fatal)
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.eval.permissions_context import (
    create_denormalized_snapshot,
    resolve_eval_values,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.eval.create import (
    create_eval as create_eval_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.logging.db_logger import get_logger


from app.infra.eval.types import (
    CreateEvalApiRequest,
    CreateEvalItem,
    EvalFieldError,
    EvalResultItem,
    CreateEvalApiResponse,
)

logger = get_logger(__name__)


async def create_eval_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: CreateEvalApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
) -> CreateEvalApiResponse:
    """Eval bulk create using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. compute_can_create — single check (applies to all items)
      3. Per-item value resolution (raw → ID, required field enforcement)
      4. Single transaction: create_eval_artifact + denormalized snapshot per item
      5. invalidate_tags
      6. sync_benchmark_entries — pre-create benchmark + invocation entries (non-fatal)
    """
    from app.infra.eval.permissions import compute_can_create

    items = request.evals

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

    # ── Step 2: Permission check ───────────────────────────────────────

    if not compute_can_create(role_level=profile.role_level, role_permissions=profile.role_permissions):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create evals.",
        )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[EvalResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_eval_values(conn, redis, item, is_create=True)
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
        return CreateEvalApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[EvalResultItem] = []
    sync_items: list[tuple] = []

    for item in items:
        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
        evals_resource_id = await create_denormalized_snapshot(
            pool,
            redis,
            id=item.resource_id,
            name_id=item.name_id,
            description_id=item.description_id,
            department_ids=item.department_ids,
            model_ids=item.model_ids,
            model_rubric_ids=item.model_rubric_ids,
            model_flag_ids=item.model_flag_ids,
            model_position_ids=item.model_position_ids,
        )

        # Combine active_flag_id with any other flag_ids
        combined_flag_ids = list(item.flag_ids or [])
        if item.active_flag_id:
            combined_flag_ids.append(item.active_flag_id)

        # Artifact create inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                result = await create_eval_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=item.department_ids,
                    flag_ids=combined_flag_ids or None,
                    model_ids=item.model_ids,
                    model_flag_ids=item.model_flag_ids,
                    model_rubric_ids=item.model_rubric_ids,
                    model_position_ids=item.model_position_ids,
                    eval_ids=[evals_resource_id],
                    soft=soft,
                )

        results.append(
            EvalResultItem(
                success=True,
                eval_id=result.id,
                message="Eval created successfully",
            )
        )
        sync_items.append((evals_resource_id, item))

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["evals"], redis=redis)

    # ── Step 6: Sync entry rows (non-fatal) ────────────────────────────

    for resource_id, item in sync_items:
        try:
            from app.infra.benchmark.sync import sync_benchmark_entries

            await sync_benchmark_entries(
                pool=pool,
                evals_resource_id=resource_id,
                model_ids=item.model_ids or [],
                model_flag_ids=item.model_flag_ids or [],
                model_rubric_ids=item.model_rubric_ids or [],
                model_position_ids=item.model_position_ids or [],
                department_ids=item.department_ids or [],
            )
        except Exception as sync_err:
            logger.warning(f"sync_benchmark_entries failed (non-fatal): {sync_err}")

    return CreateEvalApiResponse(results=results)
