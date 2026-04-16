"""Provider update logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.provider.permissions_context import (
    create_denormalized_snapshot,
    resolve_provider_permissions_context,
    resolve_provider_values,
)
from app.infra.provider.refresh import refresh_provider_impl
from app.infra.provider.types import (
    UpdateProviderApiRequest,
    UpdateProviderApiResponse,
)
from app.tools.artifacts.provider.update import _UNSET
from app.tools.artifacts.provider.update import (
    update_provider as update_provider_artifact,
)


async def update_provider_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdateProviderApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdateProviderApiResponse:
    """Provider bulk update using composable infra functions."""
    from app.infra.provider.permissions import compute_can_edit
    from app.infra.provider.types import ProviderResultItem

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    items = request.providers

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
            perms = await resolve_provider_permissions_context(conn, item.provider_id)
            if not perms.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Provider {item.provider_id} not found.",
                )
            if not compute_can_edit(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
                provider_department_ids=perms.department_ids,
                active_model_count=perms.active_model_count,
                user_department_ids=profile.department_ids,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this provider.",
                )

    if accept is not None and idempotency_key is not None:
        if not accept:
            return UpdateProviderApiResponse(
                results=[
                    ProviderResultItem(
                        success=True,
                        provider_id=item.provider_id,
                        message="Update rejected",
                    )
                    for item in items
                ],
                idempotency_key=idempotency_key,
            )
        soft = False

    has_errors = False
    error_results: list[ProviderResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_provider_values(
                conn,
                redis,
                item,
                is_create=False,
            )
            if item_errors:
                has_errors = True
                error_results.append(
                    ProviderResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(ProviderResultItem(success=True, message="Validated"))

    if has_errors:
        return UpdateProviderApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    results: list[ProviderResultItem] = []

    for item in items:
        providers_resource_id = None
        if not soft:
            providers_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
            )

        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_provider_artifact(
                    conn,
                    item.provider_id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id if item.description_id else _UNSET,
                    department_ids=item.department_ids,
                    endpoint_ids=item.endpoint_ids,
                    flag_ids=[item.active_flag_id] if item.active_flag_id else None,
                    key_ids=item.key_ids,
                    provider_ids=[providers_resource_id] if providers_resource_id else None,
                    value_id=item.value_id,
                    soft=soft,
                )

        results.append(
            ProviderResultItem(
                success=True,
                provider_id=item.provider_id,
                message="Provider updated (pending acceptance)" if soft else "Provider updated successfully",
            )
        )

    if not soft:
        await refresh_provider_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (results[0].provider_id if results else None),
        )

    return UpdateProviderApiResponse(
        results=results,
        idempotency_key=idempotency_key,
    )
