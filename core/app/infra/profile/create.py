"""Profile create logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile.permissions_context import (
    create_denormalized_snapshot,
    resolve_profile_values,
)
from app.infra.profile.refresh import refresh_profile_impl
from app.infra.profile.types import (
    CreateProfileApiRequest,
    CreateProfileApiResponse,
    ProfileResultItem,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.profile.create import (
    create_profile as create_profile_artifact,
)


async def create_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: CreateProfileApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> CreateProfileApiResponse:
    """Profile bulk create using composable infra functions."""
    from app.infra.profile.permissions import compute_can_create

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    items = request.profiles
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

    if not compute_can_create(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
        department_ids=None,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create profiles.",
        )

    if accept is not None and idempotency_key is not None:
        if not accept:
            return CreateProfileApiResponse(
                results=[
                    ProfileResultItem(
                        success=True,
                        profile_id=idempotency_key,
                        message="Profile rejected",
                    )
                ],
                idempotency_key=idempotency_key,
            )

        soft = False
    has_errors = False
    error_results: list[ProfileResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_profile_values(
                conn,
                redis,
                item,
                is_create=True,
            )
            if item_errors:
                has_errors = True
                error_results.append(
                    ProfileResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(ProfileResultItem(success=True, message="Validated"))

    if has_errors:
        return CreateProfileApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    results: list[ProfileResultItem] = []

    async with pool.acquire() as conn:
        async with conn.transaction():
            for item in items:
                profiles_resource_id = None
                if not soft:
                    profiles_resource_id = await create_denormalized_snapshot(
                        conn,
                        redis,
                        id=item.resource_id,
                        name_id=item.name_id,
                        department_ids=item.department_ids,
                        email_ids=item.email_ids,
                        role_id=item.role_id,
                    )

                result = await create_profile_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    department_ids=item.department_ids,
                    flag_ids=[item.active_flag_id] if item.active_flag_id else None,
                    email_ids=item.email_ids,
                    role_ids=[item.role_id] if item.role_id else None,
                    profile_ids=[profiles_resource_id] if profiles_resource_id else None,
                    redis=redis,
                    soft=soft,
                )

                results.append(
                    ProfileResultItem(
                        success=True,
                        profile_id=result.id,
                        message=(
                            "Profile accepted"
                            if accept is not None and idempotency_key is not None
                            else "Profile created (pending acceptance)"
                            if soft
                            else "Profile created successfully"
                        ),
                    )
                )

    if not soft:
        await refresh_profile_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (results[0].profile_id if results else None),
        )

    return CreateProfileApiResponse(
        results=results,
        idempotency_key=idempotency_key,
    )
