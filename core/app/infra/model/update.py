"""Model update logic — composable infra architecture."""

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
from app.infra.model.refresh import refresh_model_impl
from app.infra.model.types import (
    ModelResultItem,
    UpdateModelApiRequest,
    UpdateModelApiResponse,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.model.update import _UNSET
from app.tools.artifacts.model.update import (
    update_model as update_model_artifact,
)


async def update_model_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdateModelApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdateModelApiResponse:
    """Model bulk update using composable infra functions."""
    from app.infra.model.permissions import compute_can_edit

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    items = request.models

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

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            perms = await resolve_model_permissions_context(conn, item.model_id)
            if not perms.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Model {item.model_id} not found.",
                )
            if not compute_can_edit(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
                model_department_ids=perms.department_ids,
                active_agent_count=perms.active_agent_count,
                user_department_ids=profile.department_ids,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this model.",
                )

    if accept is not None and idempotency_key is not None:
        if not accept:
            return UpdateModelApiResponse(
                results=[
                    ModelResultItem(
                        success=True,
                        model_id=item.model_id,
                        message="Update rejected",
                    )
                    for item in items
                ],
                idempotency_key=idempotency_key,
            )
        soft = False

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
        return UpdateModelApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    results: list[ModelResultItem] = []

    for item in items:
        models_resource_id = None
        if not soft:
            models_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                provider_id=item.provider_id,
                temperature_level_ids=item.temperature_level_ids,
                reasoning_level_ids=item.reasoning_level_ids,
                quality_ids=item.quality_ids,
                voice_ids=item.voice_ids,
                modality_ids=item.modality_ids,
                value_id=item.value_id,
            )

        combined_flag_ids = list(item.flag_ids or [])
        if item.active_flag_id:
            combined_flag_ids.append(item.active_flag_id)

        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_model_artifact(
                    conn,
                    item.model_id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id if item.description_id else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=combined_flag_ids or None,
                    modality_ids=item.modality_ids,
                    model_ids=[models_resource_id] if models_resource_id else None,
                    pricing_ids=item.pricing_ids,
                    provider_id=item.provider_id,
                    quality_ids=item.quality_ids,
                    reasoning_level_ids=item.reasoning_level_ids,
                    temperature_level_ids=item.temperature_level_ids,
                    value_id=item.value_id,
                    voice_ids=item.voice_ids,
                    soft=soft,
                )

        results.append(
            ModelResultItem(
                success=True,
                model_id=item.model_id,
                message=(
                    "Model update accepted"
                    if accept is not None and idempotency_key is not None
                    else "Model updated (pending acceptance)"
                    if soft
                    else "Model updated successfully"
                ),
            )
        )

    if not soft:
        await refresh_model_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (results[0].model_id if results else None),
        )

    return UpdateModelApiResponse(
        results=results,
        idempotency_key=idempotency_key,
    )
