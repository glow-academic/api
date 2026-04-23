"""Setting delete logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.delete.delete_artifact import restore_artifacts
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.setting.permissions import compute_can_delete
from app.infra.setting.permissions_context import resolve_setting_permissions_context
from app.infra.setting.refresh import refresh_setting_impl
from app.infra.setting.types import (
    DeleteSettingApiResponse,
    DeleteSettingResult,
)
from app.tools.artifacts.setting.delete import delete_settings
from app.tools.artifacts.setting.get import get_settings
from app.tools.resources.names.get import get_names


async def delete_setting_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    ids: list[UUID],
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> DeleteSettingApiResponse:
    """Setting bulk delete using composable infra functions."""
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
        for idx, setting_id in enumerate(ids):
            ctx = await resolve_setting_permissions_context(conn, setting_id)
            if not ctx.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Setting {setting_id} not found.",
                )
            if not compute_can_delete(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
                setting_department_ids=ctx.department_ids,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this setting.",
                )

    if accept is not None and idempotency_key is not None:
        if not accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await restore_artifacts(
                        conn,
                        table="setting_artifact",
                        ids=ids,
                    )
        await refresh_setting_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )
        return DeleteSettingApiResponse(
            results=[
                DeleteSettingResult(
                    success=True,
                    setting_id=setting_id,
                    message=(
                        "Delete confirmed"
                        if accept
                        else "Delete rejected — setting restored"
                    ),
                )
                for setting_id in ids
            ],
            idempotency_key=idempotency_key,
        )

    name_map: dict[UUID, str] = {}
    async with pool.acquire() as conn:
        artifacts = await get_settings(conn, ids, names=True)
        for artifact in artifacts:
            name = "Unknown"
            if artifact.name_ids:
                name_resources = await get_names(conn, artifact.name_ids, redis)
                if name_resources:
                    name = name_resources[0].name or "Unknown"
            name_map[artifact.id] = name

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await delete_settings(conn, ids, soft=soft)

    await refresh_setting_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=idempotency_key or (result.deleted_ids[0] if result.deleted_ids else None),
    )

    return DeleteSettingApiResponse(
        results=[
            DeleteSettingResult(
                success=True,
                setting_id=setting_id,
                message=(
                    f"Setting '{name_map.get(setting_id, 'Unknown')}' deleted (pending confirmation)"
                    if soft
                    else f"Setting '{name_map.get(setting_id, 'Unknown')}' deleted successfully"
                ),
            )
            for setting_id in result.deleted_ids
        ],
        idempotency_key=idempotency_key,
    )
