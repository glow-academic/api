"""Profile delete logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile.permissions import compute_can_delete
from app.infra.profile.permissions_context import resolve_profile_permissions_context
from app.infra.profile.refresh import refresh_profile_impl
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.profile.types import (
    DeleteProfileApiResponse,
    DeleteProfileResult,
)
from app.infra.delete.delete_artifact import restore_artifacts
from app.tools.artifacts.profile.delete import delete_profiles
from app.tools.artifacts.profile.get import get_profiles
from app.tools.resources.names.get import get_names


async def delete_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    profile_ids: list[UUID],
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> DeleteProfileApiResponse:
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
        for idx, target_id in enumerate(profile_ids):
            ctx = await resolve_profile_permissions_context(conn, target_id)

            if not ctx.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Profile {target_id} not found.",
                )

            target_ctx = await resolve_profile_identity_context(pool, target_id, redis)
            target_role = target_ctx.role if target_ctx else None

            if not compute_can_delete(
                role_level=profile.role_level, role_permissions=profile.role_permissions,
                target_is_self=(target_id == profile_id),
                target_role=target_role,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this profile.",
                )

    if accept is not None and idempotency_key is not None:
        if not accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await restore_artifacts(
                        conn,
                        table="profile_artifact",
                        ids=profile_ids,
                    )
        await refresh_profile_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )
        return DeleteProfileApiResponse(
            results=[
                DeleteProfileResult(
                    success=True,
                    profile_id=target_id,
                    message=(
                        "Delete confirmed"
                        if accept
                        else "Delete rejected — profile restored"
                    ),
                )
                for target_id in profile_ids
            ],
            idempotency_key=idempotency_key,
        )

    async with pool.acquire() as conn:
        name_map: dict[UUID, str] = {}
        artifacts = await get_profiles(conn, profile_ids, names=True)
        for artifact in artifacts:
            name = "Unknown"
            if artifact.name_ids:
                name_resources = await get_names(conn, artifact.name_ids, redis)
                if name_resources:
                    name = name_resources[0].name or "Unknown"
            name_map[artifact.id] = name

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await delete_profiles(conn, profile_ids, soft=soft)

    await refresh_profile_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=idempotency_key or (result.deleted_ids[0] if result.deleted_ids else None),
    )

    results = [
        DeleteProfileResult(
            success=True,
            profile_id=pid,
            message=(
                f"Profile '{name_map.get(pid, 'Unknown')}' deleted (pending confirmation)"
                if soft
                else f"Profile '{name_map.get(pid, 'Unknown')}' deleted successfully"
            ),
        )
        for pid in result.deleted_ids
    ]

    return DeleteProfileApiResponse(
        results=results,
        idempotency_key=idempotency_key,
    )
