"""Provider create logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.provider.permissions_context import (
    create_denormalized_snapshot,
    resolve_provider_values,
)
from app.infra.provider.refresh import refresh_provider_impl
from app.infra.provider.types import (
    CreateProviderApiRequest,
    CreateProviderApiResponse,
    ProviderResultItem,
)
from app.tools.artifacts.provider.create import (
    create_provider as create_provider_artifact,
)


async def create_provider_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: CreateProviderApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> CreateProviderApiResponse:
    """Provider bulk create using composable infra functions."""
    from app.infra.provider.permissions import compute_can_create

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    items = request.providers
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

    requested_department_ids = [
        department_id
        for item in items
        for department_id in (item.department_ids or [])
    ]
    if not compute_can_create(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
        department_ids=requested_department_ids or None,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create providers.",
        )

    if accept is not None and idempotency_key is not None:
        if not accept:
            return CreateProviderApiResponse(
                results=[
                    ProviderResultItem(
                        success=True,
                        provider_id=idempotency_key,
                        message="Provider rejected",
                    )
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
                is_create=True,
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
        return CreateProviderApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    results: list[ProviderResultItem] = []
    snapshot_ids: list[UUID] = []

    if not soft:
        for item in items:
            providers_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                id=item.resource_id,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                endpoint=item.endpoint,
                key=item.key,
                value=item.value,
            )
            snapshot_ids.append(providers_resource_id)

    async with pool.acquire() as conn:
        async with conn.transaction():
            for idx, item in enumerate(items):
                result = await create_provider_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=item.department_ids,
                    endpoint_ids=item.endpoint_ids,
                    flag_ids=[item.active_flag_id] if item.active_flag_id else None,
                    key_ids=item.key_ids,
                    provider_ids=[snapshot_ids[idx]] if snapshot_ids else None,
                    value_id=item.value_id,
                    soft=soft,
                )

                results.append(
                    ProviderResultItem(
                        success=True,
                        provider_id=result.id,
                        message=(
                            "Provider accepted"
                            if accept is not None and idempotency_key is not None
                            else "Provider created (pending acceptance)"
                            if soft
                            else "Provider created successfully"
                        ),
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

    return CreateProviderApiResponse(
        results=results,
        idempotency_key=idempotency_key,
    )
