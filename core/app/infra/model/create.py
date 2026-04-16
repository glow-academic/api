"""Model create logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.model.permissions_context import (
    create_denormalized_snapshot,
    resolve_model_values,
)
from app.infra.model.refresh import refresh_model_impl
from app.infra.model.types import (
    CreateModelApiRequest,
    CreateModelApiResponse,
    ModelResultItem,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.model.create import (
    create_model as create_model_artifact,
)


async def create_model_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: CreateModelApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> CreateModelApiResponse:
    """Model bulk create using composable infra functions."""
    from app.infra.model.permissions import compute_can_create

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    items = request.models
    if idempotency_key is not None and len(items) == 1 and items[0].id is None:
        items = [items[0].model_copy(update={"id": idempotency_key})]

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

    if not compute_can_create(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
        department_ids=profile.department_ids,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create models.",
        )

    if accept is not None and idempotency_key is not None:
        if not accept:
            return CreateModelApiResponse(
                results=[
                    ModelResultItem(
                        success=True,
                        model_id=idempotency_key,
                        message="Model rejected",
                    )
                ],
                idempotency_key=idempotency_key,
            )
        soft = False

    has_errors = False
    error_results: list[ModelResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_model_values(conn, redis, item, is_create=True)
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
        return CreateModelApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    results: list[ModelResultItem] = []
    snapshot_ids: list[UUID] = []

    if not soft:
        for item in items:
            models_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                id=item.resource_id,
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
                value=item.value,
            )
            snapshot_ids.append(models_resource_id)

    async with pool.acquire() as conn:
        async with conn.transaction():
            for idx, item in enumerate(items):
                combined_flag_ids = list(item.flag_ids or [])
                if item.active_flag_id:
                    combined_flag_ids.append(item.active_flag_id)

                result = await create_model_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=item.department_ids,
                    flag_ids=combined_flag_ids or None,
                    modality_ids=item.modality_ids,
                    model_ids=[snapshot_ids[idx]] if snapshot_ids else None,
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
                        model_id=result.id,
                        message=(
                            "Model accepted"
                            if accept is not None and idempotency_key is not None
                            else "Model created (pending acceptance)"
                            if soft
                            else "Model created successfully"
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

    return CreateModelApiResponse(
        results=results,
        idempotency_key=idempotency_key,
    )
