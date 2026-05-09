"""Setting update logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.setting.hydrate_list_rows import hydrate_setting_list_rows
from app.infra.setting.permissions_context import (
    create_denormalized_snapshot,
    resolve_setting_permissions_context,
    resolve_setting_values,
)
from app.infra.setting.refresh import refresh_setting_impl
from app.infra.setting.types import (
    SettingResultItem,
    UpdateSettingApiRequest,
    UpdateSettingApiResponse,
)
from app.tools.artifacts.setting.get import get_settings as get_setting_artifacts
from app.tools.artifacts.setting.update import _UNSET
from app.tools.artifacts.setting.update import (
    update_setting as update_setting_artifact,
)
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls

ARTIFACT = "setting"


async def update_setting_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdateSettingApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdateSettingApiResponse:
    """Setting bulk update using composable infra functions.

    Three call shapes:
      - First call (explicit): ``request.settings`` required.
      - First call (all-matching): ``request.all=true`` plus ``patch``
        and filter fields. The impl resolves matching ids, clones the
        ``patch`` per id (stamping the resolved id), and runs the
        existing per-row update flow. Per-row permission failures
        soft-skip (returned in results).
      - Ack call: ``idempotency_key`` + ``accept`` only — locates the
        dormant update by the operation key.
    """
    from app.infra.setting.permissions import compute_can_edit

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    # ── Short-circuit: ack path ───────────────────────────────────────
    # MUST run before per-row checks: under ack, ``request.settings`` is
    # None and the dormant artifact is located by ``idempotency_key``
    # alone. Mirrors the persona/scenario pattern (batch-1 lesson #1).
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "update":
            raise HTTPException(
                status_code=404,
                detail="No pending setting update for this call.",
            )
        target_id = entry.artifact_id

        if not accept:
            async with pool.acquire() as conn:
                await create_soft_call(
                    conn,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation="update",
                    artifact_id=target_id,
                    status="rejected",
                )
            async with pool.acquire() as conn:
                await refresh_soft_calls(conn)
            return UpdateSettingApiResponse(
                results=[
                    SettingResultItem(
                        success=True,
                        setting_id=target_id,
                        message="Update rejected",
                    )
                ],
                idempotency_key=idempotency_key,
            )
        # accept=True falls through into the regular update path with
        # soft=False. The settings list (when provided) is re-applied
        # to clear any pending state. When ``request.settings`` is None
        # this is a no-op promotion — the dormant artifact already
        # carries the patch.
        if not request.settings:
            async with pool.acquire() as conn:
                await create_soft_call(
                    conn,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation="update",
                    artifact_id=target_id,
                    status="accepted",
                )
            async with pool.acquire() as conn:
                await refresh_soft_calls(conn)
            await refresh_setting_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                operation_key=idempotency_key,
            )
            return UpdateSettingApiResponse(
                results=[
                    SettingResultItem(
                        success=True,
                        setting_id=target_id,
                        message="Update accepted",
                    )
                ],
                idempotency_key=idempotency_key,
            )
        soft = False

    # ── All-matching path: resolve ids + synthesize per-row items ─────
    # Past the ack short-circuit and ``all=true`` ⇒ enumerate every
    # setting matching the filter, then clone ``request.patch`` per
    # id (stamping the resolved id). The downstream per-row flow runs
    # unchanged. Per-row permission failures soft-skip (collected into
    # ``skipped_results`` and threaded into the final response).
    skipped_results: list[SettingResultItem] = []

    if request.all:
        if request.patch is None:
            raise HTTPException(
                status_code=400,
                detail="`patch` is required when `all=true` "
                "(it carries the shared change set applied to every matched row).",
            )
        from app.infra.setting.resolve_matching_ids import resolve_matching_setting_ids
        from app.infra.setting.types import UpdateSettingItem

        matching = await resolve_matching_setting_ids(
            pool, redis,
            profile_id=profile_id,
            search=request.search,
            flag_ids=request.flag_ids,
            provider_ids=request.provider_ids,
            auth_ids=request.auth_ids,
            system_ids=request.system_ids,
            filter_department_ids=request.filter_department_ids,
            flag_search=request.flag_search,
            provider_search=request.provider_search,
            auth_search=request.auth_search,
            system_search=request.system_search,
            department_search=request.department_search,
        )
        excluded = set(request.excluded_ids or [])
        resolved_ids = [sid for sid in matching if sid not in excluded]

        if not resolved_ids:
            # Empty matching set — well-formed intent, just no rows.
            return UpdateSettingApiResponse(
                results=[], idempotency_key=idempotency_key,
            )

        # Clone the patch per matched row, stamping the resolved id.
        # ``model_dump(exclude_unset=True, exclude={"id"})`` keeps sparse
        # semantics — only fields the client actually set are written.
        patch_fields = request.patch.model_dump(exclude_unset=True, exclude={"id"})
        synth_items = [UpdateSettingItem(id=sid, **patch_fields) for sid in resolved_ids]
        # Splice into the request shape downstream code expects.
        request = request.model_copy(update={"settings": synth_items})

    # ── First-call requirements ───────────────────────────────────────
    if not request.settings:
        raise HTTPException(
            status_code=400,
            detail="`request.settings` is required for first-call update "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with `patch` and filter fields).",
        )

    items = request.settings

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

    # ── Per-item permission check ──────────────────────────────────────
    # Explicit path fails fast (existing behavior). All-matching path
    # soft-skips so the response carries per-row outcomes without
    # aborting rows the user CAN edit.
    is_all_matching = bool(request.all)
    permitted_items: list = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            perms = await resolve_setting_permissions_context(conn, item.id)
            if not perms.exists:
                if is_all_matching:
                    skipped_results.append(SettingResultItem(
                        success=False, setting_id=item.id,
                        message=f"Setting {item.id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Setting {item.id} not found.",
                )
            if not compute_can_edit(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
                setting_department_ids=perms.department_ids,
                user_department_ids=profile.department_ids,
            ):
                if is_all_matching:
                    skipped_results.append(SettingResultItem(
                        success=False, setting_id=item.id,
                        message=f"No permission to update setting {item.id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this setting.",
                )
            permitted_items.append(item)

    if is_all_matching:
        items = permitted_items
        if not items:
            return UpdateSettingApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    has_errors = False
    error_results: list[SettingResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_setting_values(conn, redis, item, is_create=False)
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
        return UpdateSettingApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    results: list[SettingResultItem] = []
    for item in items:
        async with pool.acquire() as conn:
            existing = await get_setting_artifacts(
                conn,
                [item.id],
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

        setting_resource_id = None
        if not soft:
            if existing:
                artifact = existing[0]
                eff_name_id = item.name_id or (
                    artifact.name_ids[0] if artifact.name_ids else None
                )
                eff_description_id = item.description_id or (
                    artifact.description_ids[0]
                    if artifact.description_ids
                    else None
                )
                eff_department_ids = (
                    item.department_ids
                    if item.department_ids is not None
                    else list(artifact.department_ids or [])
                )
                eff_provider_key_ids = (
                    item.provider_key_ids
                    if item.provider_key_ids is not None
                    else list(artifact.provider_key_ids or [])
                )
                eff_system_ids = (
                    item.system_ids
                    if item.system_ids is not None
                    else list(artifact.systems_ids or [])
                )
            else:
                eff_name_id = item.name_id
                eff_description_id = item.description_id
                eff_department_ids = item.department_ids
                eff_provider_key_ids = item.provider_key_ids
                eff_system_ids = item.system_ids

            setting_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                name_id=eff_name_id,
                description_id=eff_description_id,
                department_ids=eff_department_ids,
                provider_key_ids=eff_provider_key_ids,
                system_ids=eff_system_ids,
                mcp_id=item.mcp_id,
            )

        # Canonical flag state: prefer item.flag_ids; fall back to legacy
        # active_flag_id during the transition.
        combined_flag_ids: list[UUID] = list(item.flag_ids or [])
        if not combined_flag_ids and item.active_flag_id:
            combined_flag_ids.append(item.active_flag_id)

        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_setting_artifact(
                    conn,
                    item.id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id if item.description_id else _UNSET,
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
                        [setting_resource_id]
                        if setting_resource_id
                        else item.setting_resource_ids
                    ),
                    soft=soft,
                )

                if soft and idempotency_key is not None:
                    await create_soft_call(
                        conn,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="update",
                        artifact_id=item.id,
                    )
                elif (
                    accept is True
                    and idempotency_key is not None
                ):
                    await create_soft_call(
                        conn,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="update",
                        artifact_id=item.id,
                        status="accepted",
                    )

        results.append(
            SettingResultItem(
                success=True,
                setting_id=item.id,
                message=(
                    "Setting update accepted"
                    if accept is not None and idempotency_key is not None
                    else "Setting updated (pending acceptance)"
                    if soft
                    else "Setting updated successfully"
                ),
            )
        )

    if (soft or accept is True) and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    if not soft:
        await refresh_setting_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (results[0].setting_id if results else None),
        )

    # Hydrate the updated rows so the client's ghost rail can swap the
    # live card without ``router.refresh()``. Skipped under soft —
    # dormant updates stay in pending state until ack-accept.
    hydrated_rows = None
    if not soft:
        hydrated_ids = [r.setting_id for r in results if r.success and r.setting_id]
        if hydrated_ids:
            hydrated_rows = await hydrate_setting_list_rows(
                pool, redis, profile_id=profile_id, setting_ids=hydrated_ids,
            )

    # All-matching path threads soft-skipped rows back into the
    # response so the client can surface "X updated, Y skipped" in
    # one toast. Explicit path's ``skipped_results`` is empty.
    return UpdateSettingApiResponse(
        results=results + skipped_results,
        settings=hydrated_rows,
        idempotency_key=idempotency_key,
    )
