"""Setting duplicate logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.infra.setting.hydrate_list_rows import hydrate_setting_list_rows
from app.infra.setting.permissions import compute_can_duplicate
from app.infra.setting.refresh import refresh_setting_impl
from app.infra.setting.types import DuplicateSettingApiResponse
from app.tools.artifacts.setting.create import (
    create_setting as create_setting_artifact,
)
from app.tools.artifacts.setting.get import get_settings
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names

ARTIFACT = "setting"


async def duplicate_setting_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    id: UUID,
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **_kwargs,
) -> DuplicateSettingApiResponse:
    """Duplicate a setting artifact."""
    setting_id = id  # alias: tools send 'id', internal code uses 'setting_id'
    with timed("profile"):
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

    with timed("permissions"):
        if not compute_can_duplicate(
            role_level=profile.role_level,
            role_permissions=profile.role_permissions,
        ):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to duplicate this setting.",
            )

    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "duplicate":
            raise HTTPException(
                status_code=404,
                detail="No pending setting duplicate for this call.",
            )
        target_id = entry.artifact_id

        if not accept:
            async with pool.acquire() as conn:
                await create_soft_call(
                    conn,
                    redis,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation="duplicate",
                    artifact_id=target_id,
                    status="rejected",
                )
            async with pool.acquire() as conn:
                await refresh_soft_calls(conn)
            return DuplicateSettingApiResponse(
                success=True,
                setting_id=target_id,
                message="Setting duplicate rejected",
                idempotency_key=idempotency_key,
            )
        # accept=True: promote dormant duplicate via the normal create path
        # with soft=False. Stamp idempotency_key so the artifact id matches.
        soft = False
        idempotency_key = target_id

    with timed("hydrate"):
      async with pool.acquire() as conn:
        originals = await get_settings(
            conn,
            [setting_id],
            names=True,
            descriptions=True,
            departments=True,
            colors=True,
            logins=True,
            auth_item_keys=True,
            provider_keys=True,
            thresholds=True,
            systems=True,
            mcp=True,
            settings=True,
            auth_item_values=True,
        )

    if not originals:
        raise HTTPException(
            status_code=404,
            detail=f"Setting {setting_id} not found.",
        )

    original = originals[0]

    async with pool.acquire() as conn:
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
            flag_type="setting_active",
            setting=True,
            limit_count=10,
        )
        inactive_match = next((flag for flag in flag_results if not flag.value), None)
        if inactive_match:
            inactive_flag_id = inactive_match.id

    with timed("db_write"):
      async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_setting_artifact(
                conn,
                id=idempotency_key,
                name_id=new_name_resource.id,
                description_id=(
                    original.description_ids[0] if original.description_ids else None
                ),
                department_ids=original.department_ids,
                flag_ids=[inactive_flag_id] if inactive_flag_id else None,
                color_ids=original.color_ids,
                logins_ids=getattr(original, "logins_ids", None),
                system_ids=original.systems_ids,
                mcp_ids=getattr(original, "mcp_ids", None),
                threshold_ids=original.threshold_ids,
                provider_key_ids=original.provider_key_ids,
                auth_item_key_ids=original.auth_item_keys_ids,
                auth_item_value_ids=original.auth_item_value_ids,
                setting_ids=original.setting_ids,
                soft=soft,
            )

            if soft and idempotency_key is not None:
                await create_soft_call(
                    conn,
                    redis,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation="duplicate",
                    artifact_id=result.id,
                )
            elif accept is True and idempotency_key is not None:
                await create_soft_call(
                    conn,
                    redis,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation="duplicate",
                    artifact_id=result.id,
                    status="accepted",
                )

    if (soft or accept is True) and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    if not soft:
        with timed("refresh"):
            await refresh_setting_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                operation_key=idempotency_key or result.id,
            )

    # Hydrate the new row so the client's ghost rail can materialize
    # the duplicated card directly. Single-element list keeps the
    # shape consistent with create/update responses. Skipped under
    # soft — dormant copy stays in pending state until ack-accept.
    hydrated_rows = None
    if not soft:
        hydrated_rows = await hydrate_setting_list_rows(
            pool, redis, profile_id=profile_id, setting_ids=[result.id],
        )

    return DuplicateSettingApiResponse(
        success=True,
        setting_id=result.id,
        message=(
            "Setting duplicate accepted"
            if accept is not None and idempotency_key is not None
            else "Setting duplicated (pending acceptance)"
            if soft
            else f"Setting '{original_name}' duplicated successfully"
        ),
        settings=hydrated_rows,
        idempotency_key=idempotency_key or result.id,
    )
