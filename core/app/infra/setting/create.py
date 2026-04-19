"""Setting create logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.setting.permissions_context import (
    create_denormalized_snapshot,
    resolve_setting_values,
)
from app.infra.setting.refresh import refresh_setting_impl
from app.infra.setting.types import (
    CreateSettingApiRequest,
    CreateSettingApiResponse,
    SettingResultItem,
)
from app.tools.artifacts.setting.create import (
    create_setting as create_setting_artifact,
)


async def create_setting_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: CreateSettingApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> CreateSettingApiResponse:
    """Setting bulk create using composable infra functions."""
    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    items = request.settings
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

    if not has_permission(profile.role_permissions, "setting", "create"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create settings.",
        )

    if accept is not None and idempotency_key is not None:
        if not accept:
            return CreateSettingApiResponse(
                results=[
                    SettingResultItem(
                        success=True,
                        setting_id=idempotency_key,
                        message="Setting rejected",
                    )
                ],
                idempotency_key=idempotency_key,
            )
        soft = False

    has_errors = False
    error_results: list[SettingResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_setting_values(conn, redis, item, is_create=True)
            if item_errors:
                has_errors = True
                error_results.append(
                    SettingResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(SettingResultItem(success=True, message="Validated"))

    if has_errors:
        return CreateSettingApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    results: list[SettingResultItem] = []
    snapshot_ids: list[UUID] = []

    if not soft:
        for item in items:
            setting_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                id=item.resource_id,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                provider_key_ids=item.provider_key_ids,
                auth_ids=item.auth_ids,
                system_ids=item.system_ids,
            )
            snapshot_ids.append(setting_resource_id)

    async with pool.acquire() as conn:
        async with conn.transaction():
            for idx, item in enumerate(items):
                result = await create_setting_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=item.department_ids,
                    flag_ids=[item.active_flag_id] if item.active_flag_id else None,
                    color_ids=item.color_ids,
                    profile_ids=item.profile_ids,
                    auth_ids=item.auth_ids,
                    provider_key_ids=item.provider_key_ids,
                    auth_item_key_ids=item.auth_item_key_ids,
                    auth_item_value_ids=item.auth_item_value_ids,
                    system_ids=item.system_ids,
                    threshold_ids=item.threshold_ids,
                    mcp_ids=item.mcp_ids,
                    logins_ids=item.logins_ids,
                    setting_ids=(
                        [snapshot_ids[idx]]
                        if snapshot_ids
                        else item.setting_resource_ids
                    ),
                    soft=soft,
                )
                results.append(
                    SettingResultItem(
                        success=True,
                        setting_id=result.id,
                        message=(
                            "Setting accepted"
                            if accept is not None and idempotency_key is not None
                            else "Setting created (pending acceptance)"
                            if soft
                            else "Setting created successfully"
                        ),
                    )
                )

    if not soft:
        await refresh_setting_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (results[0].setting_id if results else None),
        )

    return CreateSettingApiResponse(
        results=results,
        idempotency_key=idempotency_key,
    )
