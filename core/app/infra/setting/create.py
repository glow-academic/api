"""Setting create logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.infra.setting.hydrate_list_rows import hydrate_setting_list_rows
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
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.utils.cache.hedged_row import transaction_with_writeback

ARTIFACT = "setting"


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
        if not has_permission(profile.role_permissions, "setting", "create"):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to create settings.",
            )

    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "create":
            raise HTTPException(
                status_code=404,
                detail="No pending setting create for this call.",
            )
        target_id = entry.artifact_id

        if not accept:
            async with pool.acquire() as conn:
                await create_soft_call(
                    conn,
                    redis,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation="create",
                    artifact_id=target_id,
                    status="rejected",
                )
            async with pool.acquire() as conn:
                await refresh_soft_calls(conn)
            return CreateSettingApiResponse(
                results=[
                    SettingResultItem(
                        success=True,
                        setting_id=target_id,
                        message="Setting rejected",
                    )
                ],
                idempotency_key=idempotency_key,
            )
        # accept=True: promote dormant artifact via the normal flow with
        # soft=False. Build a synthetic single-item create request stamped
        # with the resolved target_id so the artifact create activates the
        # correct row.
        soft = False
        items = [items[0].model_copy(update={"id": target_id})] if items else items

    has_errors = False
    error_results: list[SettingResultItem] = []

    with timed("resolve_values"):
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
      with timed("snapshot"):
        for item in items:
            setting_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                id=item.resource_id,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                provider_key_ids=item.provider_key_ids,
                system_ids=item.system_ids,
                mcp_id=item.mcp_id,
            )
            snapshot_ids.append(setting_resource_id)

    with timed("db_write"):
      async with pool.acquire() as conn:
        async with transaction_with_writeback(conn):
            for idx, item in enumerate(items):
                # Canonical flag state: prefer item.flag_ids; fall back to legacy
                # active_flag_id during the transition.
                combined_flag_ids: list[UUID] = list(item.flag_ids or [])
                if not combined_flag_ids and item.active_flag_id:
                    combined_flag_ids.append(item.active_flag_id)

                result = await create_setting_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=item.department_ids,
                    flag_ids=combined_flag_ids or None,
                    color_ids=item.color_ids,
                    logins_ids=item.logins_ids,
                    system_ids=item.system_ids,
                    mcp_ids=[item.mcp_id] if item.mcp_id else None,
                    threshold_ids=item.threshold_ids,
                    provider_key_ids=item.provider_key_ids,
                    auth_item_key_ids=item.auth_item_key_ids,
                    auth_item_value_ids=item.auth_item_value_ids,
                    auth_ids=item.auth_ids,
                    provider_ids=item.provider_ids,
                    setting_ids=(
                        [snapshot_ids[idx]]
                        if snapshot_ids
                        else item.setting_resource_ids
                    ),
                    soft=soft,
                )

                # Soft-write: pending ledger row tied to this tool call.
                # Promote (accept=True path): accepted ledger row.
                if soft and idempotency_key is not None:
                    await create_soft_call(
                        conn,
                        redis,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="create",
                        artifact_id=result.id,
                    )
                elif (
                    accept is True
                    and idempotency_key is not None
                ):
                    await create_soft_call(
                        conn,
                        redis,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="create",
                        artifact_id=result.id,
                        status="accepted",
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
                soft=soft,
                operation_key=idempotency_key or (results[0].setting_id if results else None),
            )

    # Hydrate the new rows so the client's ghost rail can materialize
    # the live card directly from the audit ``.completed`` payload.
    # Skipped under ``soft=True`` — the dormant artifact isn't fully
    # active until ack-accept, so an empty ``settings`` field is the
    # right signal for the ghost to stay in pending state.
    hydrated_rows = None
    if not soft:
        with timed("hydrate"):
            hydrated_ids = [r.setting_id for r in results if r.success and r.setting_id]
            if hydrated_ids:
                hydrated_rows = await hydrate_setting_list_rows(
                    pool, redis, profile_id=profile_id, setting_ids=hydrated_ids,
                )

    return CreateSettingApiResponse(
        results=results,
        settings=hydrated_rows,
        idempotency_key=idempotency_key,
    )
