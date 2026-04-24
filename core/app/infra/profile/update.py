"""Profile update logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile.permissions_context import (
    create_denormalized_snapshot,
    resolve_profile_permissions_context,
    resolve_profile_values,
)
from app.infra.profile.refresh import refresh_profile_impl
from app.infra.profile.types import (
    UpdateProfileApiRequest,
    UpdateProfileApiResponse,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.profile.get import (
    get_profiles as get_profile_artifacts,
)
from app.tools.artifacts.profile.update import _UNSET
from app.tools.artifacts.profile.update import (
    update_profile as update_profile_artifact,
)


async def update_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdateProfileApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdateProfileApiResponse:
    """Profile bulk update using composable infra functions."""
    from app.infra.profile.permissions import compute_can_edit
    from app.infra.profile.types import ProfileResultItem

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    items = request.profiles

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

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            target_is_self = item.profile_id == profile_id
            perms = await resolve_profile_permissions_context(conn, item.profile_id)
            if not perms.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Profile {item.profile_id} not found.",
                )
            if not compute_can_edit(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
                target_is_self=target_is_self,
                target_department_ids=perms.department_ids,
                user_department_ids=profile.department_ids,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this profile.",
                )

    if accept is not None and idempotency_key is not None:
        if not accept:
            return UpdateProfileApiResponse(
                results=[
                    ProfileResultItem(
                        success=True,
                        profile_id=item.profile_id,
                        message="Update rejected",
                    )
                    for item in items
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
                is_create=False,
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
        return UpdateProfileApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    results: list[ProfileResultItem] = []

    for item in items:
        async with pool.acquire() as conn:
            existing = await get_profile_artifacts(
                conn,
                [item.profile_id],
                names=True,
                departments=True,
                roles=True,
                emails=True,
            )

        if existing:
            artifact = existing[0]
            eff_name_id = item.name_id or (artifact.name_ids[0] if artifact.name_ids else None)
            eff_department_ids = (
                item.department_ids
                if item.department_ids is not None
                else list(artifact.department_ids or [])
            )
            eff_role_id = (
                item.role_id
                if item.role_id is not None
                else (artifact.role_ids[0] if artifact.role_ids else None)
            )
            eff_email_ids = (
                item.email_ids
                if item.email_ids is not None
                else list(artifact.email_ids or [])
            )
        else:
            eff_name_id = item.name_id
            eff_department_ids = item.department_ids
            eff_role_id = item.role_id
            eff_email_ids = item.email_ids

        profiles_resource_id = None
        if not soft:
            async with pool.acquire() as conn:
                profiles_resource_id = await create_denormalized_snapshot(
                    conn,
                    redis,
                    name_id=eff_name_id,
                    department_ids=eff_department_ids,
                    email_ids=eff_email_ids,
                    role_id=eff_role_id,
                )

        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_profile_artifact(
                    conn,
                    item.profile_id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=item.flag_ids or None,
                    email_ids=item.email_ids,
                    role_ids=[item.role_id] if item.role_id else None,
                    profile_ids=[profiles_resource_id] if profiles_resource_id else None,
                    redis=redis,
                    soft=soft,
                )

        results.append(
            ProfileResultItem(
                success=True,
                profile_id=item.profile_id,
                message="Profile updated (pending acceptance)" if soft else "Profile updated successfully",
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

    return UpdateProfileApiResponse(
        results=results,
        idempotency_key=idempotency_key,
    )
