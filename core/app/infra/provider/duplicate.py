"""Provider duplicate logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.provider.permissions import compute_can_duplicate
from app.infra.provider.refresh import refresh_provider_impl
from app.infra.provider.types import (
    DuplicateProviderApiResponse,
)
from app.tools.artifacts.provider.create import (
    create_provider as create_provider_artifact,
)
from app.tools.artifacts.provider.get import get_providers
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names


async def duplicate_provider_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    id: UUID,
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> DuplicateProviderApiResponse:
    """Duplicate a provider artifact."""
    provider_id = id  # alias: tools send 'id', internal code uses 'provider_id'
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

    if not compute_can_duplicate(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to duplicate this provider.",
        )

    if accept is not None and idempotency_key is not None:
        if not accept:
            return DuplicateProviderApiResponse(
                success=True,
                provider_id=idempotency_key,
                message="Provider duplicate rejected",
                idempotency_key=idempotency_key,
            )

        async with pool.acquire() as conn:
            async with conn.transaction():
                result = await create_provider_artifact(
                    conn,
                    id=idempotency_key,
                    soft=False,
                )

        await refresh_provider_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )

        return DuplicateProviderApiResponse(
            success=True,
            provider_id=result.id,
            message="Provider duplicate accepted",
            idempotency_key=idempotency_key,
        )

    async with pool.acquire() as conn:
        originals = await get_providers(
            conn,
            [provider_id],
            names=True,
            descriptions=True,
            departments=True,
            endpoints=True,
            keys=True,
            values=True,
            providers=True,
        )

        if not originals:
            raise HTTPException(
                status_code=404,
                detail=f"Provider {provider_id} not found.",
            )

        original = originals[0]
        original_name = "Unknown"
        if original.name_ids:
            name_resources = await get_names(pool, original.name_ids, redis)
            if name_resources:
                original_name = name_resources[0].name or "Unknown"

        new_name_resource = await create_name(conn, f"{original_name} Copy", redis)

        inactive_flag_id: UUID | None = None
        flag_results = await search_flags(
            conn,
            redis,
            flag_type="provider_active",
            provider=True,
            limit_count=10,
        )
        inactive_match = next((flag for flag in flag_results if not flag.value), None)
        if inactive_match:
            inactive_flag_id = inactive_match.id

    flag_ids = [inactive_flag_id] if inactive_flag_id else None

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_provider_artifact(
                conn,
                id=idempotency_key,
                name_id=new_name_resource.id,
                description_id=original.description_ids[0] if original.description_ids else None,
                department_ids=original.department_ids,
                endpoint_ids=original.endpoint_ids,
                key_ids=original.key_ids,
                value_id=original.value_id,
                provider_ids=original.provider_ids,
                flag_ids=flag_ids,
                soft=soft,
            )

    if not soft:
        await refresh_provider_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key or result.id,
        )

    return DuplicateProviderApiResponse(
        success=True,
        provider_id=result.id,
        message="Provider duplicated (pending acceptance)" if soft else f"Provider '{original_name}' duplicated successfully",
        idempotency_key=idempotency_key,
    )
