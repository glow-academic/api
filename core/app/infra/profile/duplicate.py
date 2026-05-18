"""Profile duplicate logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile.permissions import compute_can_duplicate
from app.infra.profile.refresh import refresh_profile_impl
from app.infra.profile.types import (
    DuplicateProfileApiResponse,
    ListProfilesApiProfile,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.profile.create import (
    create_profile as create_profile_artifact,
)
from app.tools.artifacts.profile.get import get_profiles
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names

ARTIFACT = "profile"


async def duplicate_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    target_profile_id: UUID,
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> DuplicateProfileApiResponse:
    """Duplicate a profile artifact."""
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
            detail="You don't have permission to duplicate this profile.",
        )

    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "duplicate":
            raise HTTPException(
                status_code=404,
                detail="No pending profile duplicate for this call.",
            )
        target_id = entry.artifact_id

        result_id = target_id
        profiles_rows_ack = None
        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    result = await create_profile_artifact(
                        conn,
                        id=target_id,
                        soft=False,
                        redis=redis,
                    )
            result_id = result.id
            from app.infra.profile.hydrate_list_rows import hydrate_profile_list_rows
            profiles_rows_ack = await hydrate_profile_list_rows(
                pool, redis, profile_id=profile_id, profile_ids=[result_id],
            )

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation="duplicate",
                artifact_id=target_id,
                status="accepted" if accept else "rejected",
            )
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

        await refresh_profile_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )

        return DuplicateProfileApiResponse(
            success=True,
            profile_id=result_id,
            message="Profile duplicate accepted" if accept else "Profile duplicate rejected",
            profiles=profiles_rows_ack,
            idempotency_key=idempotency_key,
        )

    async with pool.acquire() as conn:
        originals = await get_profiles(
            conn,
            [target_profile_id],
            names=True,
            departments=True,
            emails=True,
            profiles=True,
            roles=True,
        )
        if not originals:
            raise HTTPException(
                status_code=404,
                detail=f"Profile {target_profile_id} not found.",
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
            flag_type="profile_active",
            profile=True,
            limit_count=10,
        )
        inactive_match = next((flag for flag in flag_results if not flag.value), None)
        if inactive_match:
            inactive_flag_id = inactive_match.id

    flag_ids = [inactive_flag_id] if inactive_flag_id else None

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_profile_artifact(
                conn,
                id=idempotency_key,
                name_id=new_name_resource.id,
                department_ids=original.department_ids,
                email_ids=None,
                role_ids=original.role_ids,
                profile_ids=original.profile_ids,
                flag_ids=flag_ids,
                redis=redis,
                soft=soft,
            )

            if soft and idempotency_key is not None:
                await create_soft_call(
                    conn,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation="duplicate",
                    artifact_id=result.id,
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
            operation_key=idempotency_key or result.id,
        )

    # Hydrate the duplicated row for the client ghost rail.
    # Soft-pending duplicates skip hydration (dormant artifact).
    profiles_rows: list[ListProfilesApiProfile] | None = None
    if not soft:
        from app.infra.profile.hydrate_list_rows import hydrate_profile_list_rows
        profiles_rows = await hydrate_profile_list_rows(
            pool, redis, profile_id=profile_id, profile_ids=[result.id],
        )

    return DuplicateProfileApiResponse(
        success=True,
        profile_id=result.id,
        message="Profile duplicated (pending acceptance)" if soft else f"Profile '{original_name}' duplicated successfully",
        profiles=profiles_rows,
        idempotency_key=idempotency_key,
    )
