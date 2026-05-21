"""Department delete logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.delete.delete_artifact import restore_artifacts
from app.infra.department.permissions import compute_can_delete
from app.infra.department.permissions_context import (
    resolve_department_permissions_context,
)
from app.infra.department.refresh import refresh_department_impl
from app.infra.department.types import (
    DeleteDepartmentApiResponse,
    DeleteDepartmentResult,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.department.delete import delete_departments
from app.tools.artifacts.department.get import get_departments
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.resources.names.get import get_names

ARTIFACT = "department"


async def delete_department_impl(
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
    flag_search: str | None = None,
) -> DeleteDepartmentApiResponse:
    """Department bulk delete using composable infra functions.

    Three call shapes:
      - First call (explicit): ``ids`` required.
      - First call (all-matching): ``all=true`` plus filter fields. The
        impl resolves matching ids via ``resolve_matching_department_ids``,
        subtracts ``excluded_ids``, then runs the existing per-row flow.
        Per-row permission failures soft-skip (returned in results)
        rather than aborting the whole call.
      - Ack call: ``idempotency_key`` + ``accept`` only — no ``ids``
        needed, the dormant deletion is located by the operation key.
    """
    from app.infra.identity.keycloak_sync import perform_keycloak_sync

    # ── Short-circuit: ack path ───────────────────────────────────────
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "delete":
            raise HTTPException(
                status_code=404,
                detail="No pending department delete for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            pass
        else:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await restore_artifacts(
                        conn, table="department_artifact", ids=[target_id],
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

        await refresh_department_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )
        try:
            await perform_keycloak_sync(department_id=str(target_id))
        except Exception:
            pass
        return DeleteDepartmentApiResponse(
            results=[
                DeleteDepartmentResult(
                    success=True,
                    department_id=target_id,
                    message="Delete confirmed" if accept else "Delete rejected — department restored",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── All-matching path: resolve ids server-side ────────────────────
    # Past the ack short-circuit and ``all=true`` ⇒ enumerate every
    # department matching the filter, then subtract ``excluded_ids``.
    # The per-row permission check below filters out anything the
    # user can't delete (soft-skip, returned in results).
    if all:
        from app.infra.department.resolve_matching_ids import (
            resolve_matching_department_ids,
        )
        matching = await resolve_matching_department_ids(
            pool, redis,
            profile_id=profile_id,
            search=search,
            flag_search=flag_search,
        )
        excluded = set(excluded_ids or [])
        ids = [did for did in matching if did not in excluded]

    # ── First-call requirements ───────────────────────────────────────
    if not ids:
        if all:
            # Empty matching set — return an empty results list rather
            # than 400. The user's intent ("delete all matching") is
            # well-formed; the universe just happens to be empty.
            return DeleteDepartmentApiResponse(results=[], idempotency_key=idempotency_key)
        raise HTTPException(
            status_code=400,
            detail="`department_ids` is required for first-call deletion "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with filter fields).",
        )

    # ── Step 1: Profile context ────────────────────────────────────────

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
    skipped_results: list[DeleteDepartmentResult] = []
    permitted_ids: list[UUID] = []

    async with pool.acquire() as conn:
        for idx, department_id in enumerate(ids):
            ctx = await resolve_department_permissions_context(conn, department_id)

            if not ctx.exists:
                if all:
                    skipped_results.append(DeleteDepartmentResult(
                        success=False, department_id=department_id,
                        message=f"Department {department_id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Department {department_id} not found.",
                )

            if not compute_can_delete(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
                total_usage=ctx.usage_count,
            ):
                if all:
                    skipped_results.append(DeleteDepartmentResult(
                        success=False, department_id=department_id,
                        message=f"No permission to delete department {department_id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this department.",
                )

            permitted_ids.append(department_id)

    # All-matching path: replace ``ids`` with the filtered set. Explicit
    # path leaves it alone (it already raised on any failure).
    if all:
        ids = permitted_ids
        if not ids:
            return DeleteDepartmentApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    # ── Step 4: Fetch names for result messages ───────────────────────

    name_map: dict[UUID, str] = {}
    async with pool.acquire() as conn:
        artifacts = await get_departments(conn, ids, names=True)
        for artifact in artifacts:
            name = "Unknown"
            if artifact.name_ids:
                name_resources = await get_names(pool, artifact.name_ids, redis)
                if name_resources:
                    name = name_resources[0].name or "Unknown"
            name_map[artifact.id] = name

    # ── Step 5: Single transaction — bulk delete ──────────────────────

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await delete_departments(conn, ids, soft=soft)

            if soft and idempotency_key is not None:
                for did in result.deleted_ids:
                    await create_soft_call(
                        conn,
                        redis,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="delete",
                        artifact_id=did,
                    )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    await refresh_department_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=idempotency_key or (result.deleted_ids[0] if result.deleted_ids else None),
    )

    if not soft:
        try:
            for department_id in result.deleted_ids:
                await perform_keycloak_sync(department_id=str(department_id))
        except Exception:
            pass

    results = [
        DeleteDepartmentResult(
            success=True,
            department_id=pid,
            message=(
                f"Department '{name_map.get(pid, 'Unknown')}' deleted (pending confirmation)"
                if soft
                else f"Department '{name_map.get(pid, 'Unknown')}' deleted successfully"
            ),
        )
        for pid in result.deleted_ids
    ]

    # All-matching path threads any soft-skipped rows back into the
    # response so the client can surface "X deleted, Y skipped" in
    # one go. Explicit-ids path's skipped_results is empty.
    return DeleteDepartmentApiResponse(
        results=results + skipped_results,
        idempotency_key=idempotency_key,
    )
