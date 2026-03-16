"""Model update logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. resolve_model_permissions_context — per-item access + edit check
  3. resolve_model_values — raw value → ID resolution
  4. update_model_artifact — junction writes (partial update)
  5. create_denormalized_snapshot — models_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.model.permissions_context import (
    create_denormalized_snapshot,
    resolve_model_permissions_context,
    resolve_model_values,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.model.update import (
    _UNSET,
)
from app.tools.artifacts.model.update import (
    update_model as update_model_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags


async def update_model_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
) -> dict:
    """Model bulk update using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. Per-item: resolve_model_permissions_context → exists + compute_can_edit
      3. Per-item value resolution (raw → ID, no required field enforcement)
      4. Single transaction: update_model_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
    from app.infra.model.permissions import compute_can_edit
    from app.infra.model.types import (
        ModelResultItem,
        UpdateModelApiResponse,
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
            perms = await resolve_model_permissions_context(conn, item.model_id)
            if not perms.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Model {item.model_id} not found.",
                )
            if not compute_can_edit(
                user_role=profile.role,
                model_department_ids=perms.department_ids,
                active_agent_count=perms.active_agent_count,
                user_department_ids=profile.department_ids,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this model.",
                )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[ModelResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_model_values(conn, redis, item, is_create=False)
            if item_errors:
                has_errors = True
                error_results.append(
                    ModelResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(ModelResultItem(success=True, message="Validated"))

    if has_errors:
        return UpdateModelApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[ModelResultItem] = []

    for item in items:
        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
        models_resource_id = await create_denormalized_snapshot(
            pool,
            redis,
            name_id=item.name_id,
            description_id=item.description_id,
            department_ids=item.department_ids,
            provider_ids=item.provider_ids,
            temperature_level_ids=item.temperature_level_ids,
            reasoning_level_ids=item.reasoning_level_ids,
            quality_ids=item.quality_ids,
            voice_ids=item.voice_ids,
            modality_ids=item.modality_ids,
            value_ids=item.value_ids,
        )

        # Artifact update inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_model_artifact(
                    conn,
                    item.model_id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id
                    if item.description_id
                    else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=item.flag_ids,
                    modality_ids=item.modality_ids,
                    model_ids=[models_resource_id],
                    pricing_ids=item.pricing_ids,
                    provider_ids=item.provider_ids,
                    quality_ids=item.quality_ids,
                    reasoning_level_ids=item.reasoning_level_ids,
                    temperature_level_ids=item.temperature_level_ids,
                    value_ids=item.value_ids,
                    voice_ids=item.voice_ids,
                )

        results.append(
            ModelResultItem(
                success=True,
                model_id=item.model_id,
                message="Model updated successfully",
            )
        )

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["models"], redis=redis)

    return UpdateModelApiResponse(results=results)
