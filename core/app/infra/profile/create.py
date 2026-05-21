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
from app.infra.profile.primary_department import (
    resolve_primary_departments_id,
)
from app.infra.profile.refresh import refresh_profile_impl
from app.infra.profile.types import (
    CreateProfileApiRequest,
    CreateProfileApiResponse,
    ListProfilesApiProfile,
    ProfileResultItem,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.profile.create import (
    create_profile as create_profile_artifact,
)
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls

ARTIFACT = "profile"


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
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "create":
            raise HTTPException(
                status_code=404,
                detail="No pending profile create for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await create_profile_artifact(
                        conn,
                        id=target_id,
                        soft=False,
                        redis=redis,
                    )

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                redis,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation="create",
                artifact_id=target_id,
                status="accepted" if accept else "rejected",
            )
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

        await refresh_profile_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            operation_key=idempotency_key,
        )

        return CreateProfileApiResponse(
            results=[
                ProfileResultItem(
                    success=True,
                    profile_id=target_id,
                    message="Profile accepted" if accept else "Profile rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )
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

                primary_departments_id = await resolve_primary_departments_id(
                    conn,
                    redis,
                    departments_id=item.primary_department_id,
                    soft=soft,
                )

                result = await create_profile_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    primary_departments_id=primary_departments_id,
                    department_ids=item.department_ids,
                    flag_ids=item.flag_ids or None,
                    email_ids=item.email_ids,
                    role_ids=[item.role_id] if item.role_id else None,
                    profile_ids=[profiles_resource_id] if profiles_resource_id else None,
                    redis=redis,
                    soft=soft,
                )

                if soft and idempotency_key is not None:
                    await create_soft_call(
                        conn,
                        redis,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="create",
                        artifact_id=result.id,
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

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    if not soft:
        await refresh_profile_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (results[0].profile_id if results else None),
        )

    # ── Hydrate full row content for the client ──────────────────────
    # See ``hydrate_profile_list_rows``: returns the same shape
    # ``/profile/search`` does. Audit framework spreads response fields
    # into ``profile.create.completed``, so the client's ghost rail
    # materializes the new row directly — no SSR refresh round-trip.
    # Soft-pending creates skip hydration: the dormant row isn't fully
    # active yet (denormalized snapshot is created on ack-accept).
    profiles_rows: list[ListProfilesApiProfile] | None = None
    if not soft:
        from app.infra.profile.hydrate_list_rows import hydrate_profile_list_rows
        new_ids = [
            r.profile_id for r in results
            if r.success and r.profile_id is not None
        ]
        if new_ids:
            profiles_rows = await hydrate_profile_list_rows(
                pool, redis, profile_id=profile_id, profile_ids=new_ids,
            )

    return CreateProfileApiResponse(
        results=results,
        profiles=profiles_rows,
        idempotency_key=idempotency_key,
    )
