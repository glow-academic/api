"""Setting delete logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.delete.delete_artifact import restore_artifacts
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.infra.setting.permissions import compute_can_delete
from app.infra.setting.permissions_context import resolve_setting_permissions_context
from app.infra.setting.refresh import refresh_setting_impl
from app.infra.setting.types import (
    DeleteSettingApiResponse,
    DeleteSettingResult,
)
from app.tools.artifacts.setting.delete import delete_settings
from app.tools.artifacts.setting.get import get_settings
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.resources.names.get import get_names

ARTIFACT = "setting"


async def delete_setting_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    ids: list[UUID] | None = None,
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    # All-matching path (additive — explicit-ids path stays untouched).
    all: bool = False,
    excluded_ids: list[UUID] | None = None,
    search: str | None = None,
    flag_ids: list[UUID] | None = None,
    provider_ids: list[UUID] | None = None,
    auth_ids: list[UUID] | None = None,
    system_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    flag_search: str | None = None,
    provider_search: str | None = None,
    auth_search: str | None = None,
    system_search: str | None = None,
    department_search: str | None = None,
) -> DeleteSettingApiResponse:
    """Setting bulk delete using composable infra functions.

    Three call shapes:
      - First call (explicit): ``ids`` required.
      - First call (all-matching): ``all=true`` plus filter fields. The
        impl resolves matching ids via ``resolve_matching_setting_ids``,
        subtracts ``excluded_ids``, then runs the existing per-row flow.
        Per-row permission failures soft-skip (returned in results)
        rather than aborting the whole call.
      - Ack call: ``idempotency_key`` + ``accept`` only — no ``ids``
        needed, the dormant deletion is located by the operation key.
    """

    # ── Short-circuit: ack path ───────────────────────────────────────
    # MUST run before per-row permission checks: under ack, ``ids`` is
    # None and the dormant artifact is located by ``idempotency_key``
    # alone. Mirrors the persona/scenario pattern (batch-1 lesson #1).
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "delete":
            raise HTTPException(
                status_code=404,
                detail="No pending setting delete for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            # Confirm deletion: no-op (already deactivated by soft delete)
            pass
        else:
            # Reject: restore soft-deleted artifact
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await restore_artifacts(
                        conn,
                        table="setting_artifact",
                        ids=[target_id],
                    )

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                redis,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation="delete",
                artifact_id=target_id,
                status="accepted" if accept else "rejected",
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
        return DeleteSettingApiResponse(
            results=[
                DeleteSettingResult(
                    success=True,
                    setting_id=target_id,
                    message=(
                        "Delete confirmed"
                        if accept
                        else "Delete rejected — setting restored"
                    ),
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── All-matching path: resolve ids server-side ────────────────────
    # Past the ack short-circuit and ``all=true`` ⇒ enumerate every
    # setting matching the filter, then subtract ``excluded_ids``.
    # The per-row permission check below filters out anything the
    # user can't delete (soft-skip, returned in results).
    if all:
        from app.infra.setting.resolve_matching_ids import resolve_matching_setting_ids
        matching = await resolve_matching_setting_ids(
            pool, redis,
            profile_id=profile_id,
            search=search,
            flag_ids=flag_ids,
            provider_ids=provider_ids,
            auth_ids=auth_ids,
            system_ids=system_ids,
            filter_department_ids=filter_department_ids,
            flag_search=flag_search,
            provider_search=provider_search,
            auth_search=auth_search,
            system_search=system_search,
            department_search=department_search,
        )
        excluded = set(excluded_ids or [])
        ids = [sid for sid in matching if sid not in excluded]

    # ── First-call requirements ───────────────────────────────────────
    if not ids:
        if all:
            # Empty matching set — return an empty results list rather
            # than 400. The user's intent ("delete all matching") is
            # well-formed; the universe just happens to be empty.
            return DeleteSettingApiResponse(
                results=[], idempotency_key=idempotency_key,
            )
        raise HTTPException(
            status_code=400,
            detail="`setting_ids` is required for first-call deletion "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with filter fields).",
        )

    # ── Step 1: Profile context ────────────────────────────────────────

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

    # ── Step 2+3: Per-item permission checks ──────────────────────────
    # Explicit-ids path fails fast (preserves existing 404/403 behavior).
    # All-matching path soft-skips: collects per-row results so the
    # toast can say "X deleted, Y skipped (no permission)" without
    # aborting rows the user CAN delete.
    skipped_results: list[DeleteSettingResult] = []
    permitted_ids: list[UUID] = []

    with timed("permissions"):
      async with pool.acquire() as conn:
        for idx, setting_id in enumerate(ids):
            ctx = await resolve_setting_permissions_context(conn, setting_id)
            if not ctx.exists:
                if all:
                    skipped_results.append(DeleteSettingResult(
                        success=False, setting_id=setting_id,
                        message=f"Setting {setting_id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Setting {setting_id} not found.",
                )
            if not compute_can_delete(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
                setting_department_ids=ctx.department_ids,
                user_department_ids=profile.department_ids,
            ):
                if all:
                    skipped_results.append(DeleteSettingResult(
                        success=False, setting_id=setting_id,
                        message=f"No permission to delete setting {setting_id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this setting.",
                )
            permitted_ids.append(setting_id)

    # All-matching path: replace ``ids`` with the filtered set. Explicit
    # path leaves it alone (it already raised on any failure).
    if all:
        ids = permitted_ids
        if not ids:
            # Every matched row was skipped — return only the skipped
            # results. No actual delete fires.
            return DeleteSettingApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    name_map: dict[UUID, str] = {}
    with timed("hydrate_names"):
      async with pool.acquire() as conn:
        artifacts = await get_settings(conn, ids, names=True)
        for artifact in artifacts:
            name = "Unknown"
            if artifact.name_ids:
                name_resources = await get_names(pool, artifact.name_ids, redis)
                if name_resources:
                    name = name_resources[0].name or "Unknown"
            name_map[artifact.id] = name

    with timed("db_write"):
      async with pool.acquire() as conn:
        async with conn.transaction():
            result = await delete_settings(conn, ids, soft=soft)

            if soft and idempotency_key is not None:
                for sid in result.deleted_ids:
                    await create_soft_call(
                        conn,
                        redis,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="delete",
                        artifact_id=sid,
                    )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    with timed("refresh"):
        await refresh_setting_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (result.deleted_ids[0] if result.deleted_ids else None),
        )

    results = [
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
    ]

    # All-matching path threads any soft-skipped rows back into the
    # response so the client can surface "X deleted, Y skipped" in
    # one go. Explicit-ids path's skipped_results is empty.
    return DeleteSettingApiResponse(
        results=results + skipped_results,
        idempotency_key=idempotency_key,
    )
