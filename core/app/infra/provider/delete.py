"""Provider delete logic — composable infra architecture.

Core delete function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. resolve_provider_permissions_context — per-item exists, departments, usage
  3. compute_can_delete — permission check
  4. delete_providers — bulk delete tool
  5. canonical refresh
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.delete.delete_artifact import restore_artifacts
from app.infra.provider.permissions import compute_can_delete
from app.infra.provider.permissions_context import resolve_provider_permissions_context
from app.infra.provider.refresh import refresh_provider_impl
from app.infra.provider.types import (
    DeleteProviderApiResponse,
    DeleteProviderResult,
)
from app.tools.artifacts.provider.delete import delete_providers
from app.tools.artifacts.provider.get import get_providers
from app.tools.resources.names.get import get_names


async def delete_provider_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    provider_ids: list[UUID],
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> DeleteProviderApiResponse:
    """Provider bulk delete using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role
      2. Per-item: resolve_provider_permissions_context -> exists, departments, usage
      3. Per-item: compute_can_delete -> permission check (fail fast)
      4. Fetch names for result messages
      5. Single transaction: delete_providers -> bulk delete
      6. canonical refresh
    """

    # -- Step 1: Profile context --------------------------------------------------

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

    # -- Step 2+3: Per-item permission checks (fail fast) -------------------------

    async with pool.acquire() as conn:
        for idx, provider_id in enumerate(provider_ids):
            ctx = await resolve_provider_permissions_context(conn, provider_id)

            if not ctx.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Provider {provider_id} not found.",
                )

            if not compute_can_delete(
                role_level=profile.role_level, role_permissions=profile.role_permissions,
                provider_department_ids=ctx.department_ids,
                active_model_count=ctx.active_model_count,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this provider.",
                )

    # -- Step 4: Ack short-circuit ------------------------------------------------

    if accept is not None and idempotency_key is not None:
        if not accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await restore_artifacts(
                        conn,
                        table="provider_artifact",
                        ids=provider_ids,
                    )
        await refresh_provider_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )
        return DeleteProviderApiResponse(
            results=[
                DeleteProviderResult(
                    success=True,
                    provider_id=provider_id,
                    message=(
                        "Delete confirmed"
                        if accept
                        else "Delete rejected — provider restored"
                    ),
                )
                for provider_id in provider_ids
            ],
            idempotency_key=idempotency_key,
        )

    # -- Step 5: Fetch names for result messages ----------------------------------

    async with pool.acquire() as conn:
        name_map: dict[UUID, str] = {}
        artifacts = await get_providers(conn, provider_ids, names=True)
        for artifact in artifacts:
            name = "Unknown"
            if artifact.name_ids:
                name_resources = await get_names(conn, artifact.name_ids, redis)
                if name_resources:
                    name = name_resources[0].name or "Unknown"
            name_map[artifact.id] = name

    # -- Step 6: Single transaction — bulk delete ---------------------------------

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await delete_providers(conn, provider_ids, soft=soft)

    # -- Step 7: Canonical refresh ------------------------------------------------

    await refresh_provider_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=idempotency_key or (result.deleted_ids[0] if result.deleted_ids else None),
    )

    results = [
        DeleteProviderResult(
            success=True,
            provider_id=pid,
            message=(
                f"Provider '{name_map.get(pid, 'Unknown')}' deleted (pending confirmation)"
                if soft
                else f"Provider '{name_map.get(pid, 'Unknown')}' deleted successfully"
            ),
        )
        for pid in result.deleted_ids
    ]

    return DeleteProviderApiResponse(
        results=results,
        idempotency_key=idempotency_key,
    )
