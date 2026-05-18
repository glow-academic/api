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
    ListProviderApiProvider,
    ProviderResultItem,
)
from app.tools.artifacts.provider.create import (
    create_provider as create_provider_artifact,
)
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls

ARTIFACT = "provider"


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
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "create":
            raise HTTPException(
                status_code=404,
                detail="No pending provider create for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await create_provider_artifact(
                        conn,
                        id=target_id,
                        soft=False,
                    )

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation="create",
                artifact_id=target_id,
                status="accepted" if accept else "rejected",
            )
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

        await refresh_provider_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            operation_key=idempotency_key,
        )

        return CreateProviderApiResponse(
            results=[
                ProviderResultItem(
                    success=True,
                    provider_id=target_id,
                    message="Provider accepted" if accept else "Provider rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

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
                    flag_ids=item.flag_ids or None,
                    key_ids=item.key_ids,
                    provider_ids=[snapshot_ids[idx]] if snapshot_ids else None,
                    value_id=item.value_id,
                    soft=soft,
                )

                if soft and idempotency_key is not None:
                    await create_soft_call(
                        conn,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="create",
                        artifact_id=result.id,
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

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    if not soft:
        await refresh_provider_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (results[0].provider_id if results else None),
        )

    # ── Hydrate full row content for the client ──────────────────────
    # See ``hydrate_provider_list_rows``: returns the same shape
    # ``/provider/search`` does. Audit framework spreads response
    # fields into ``provider.create.completed``, so the client's
    # ghost rail materializes the new row directly — no SSR refresh
    # round-trip. Soft-pending creates skip hydration: the dormant
    # row isn't fully active yet (denormalized snapshot is created
    # on ack-accept).
    providers: list[ListProviderApiProvider] | None = None
    if not soft:
        from app.infra.provider.hydrate_list_rows import hydrate_provider_list_rows
        new_ids = [r.provider_id for r in results if r.success and r.provider_id is not None]
        if new_ids:
            providers = await hydrate_provider_list_rows(
                pool, redis, profile_id=profile_id, provider_ids=new_ids,
            )

    return CreateProviderApiResponse(
        results=results,
        idempotency_key=idempotency_key,
        providers=providers,
    )
