"""Auth delete logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.auth.permissions import compute_can_delete
from app.infra.auth.permissions_context import resolve_auth_permissions_context
from app.infra.auth.refresh import refresh_auth_impl
from app.infra.auth.types import DeleteAuthApiResponse, DeleteAuthResult
from app.infra.delete.delete_artifact import restore_artifacts
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.auth.delete import delete_auths
from app.tools.artifacts.auth.get import get_auths
from app.tools.resources.names.get import get_names


async def delete_auth_impl(
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
    filter_department_ids: list[UUID] | None = None,
    department_search: str | None = None,
    flag_search: str | None = None,
) -> DeleteAuthApiResponse:
    """Auth bulk delete using composable infra functions.

    Three call shapes:
      - First call (explicit): ``ids`` required.
      - First call (all-matching): ``all=true`` plus filter fields. The
        impl resolves matching ids via ``resolve_matching_auth_ids``,
        subtracts ``excluded_ids``, then runs the existing per-row flow.
        Per-row permission failures soft-skip (returned in results)
        rather than aborting the whole call.
      - Ack call: ``idempotency_key`` + ``accept`` only — no ``ids``
        needed, the dormant deletion is located by the operation key.
    """
    from app.infra.identity.keycloak_sync import perform_keycloak_sync

    # ── Short-circuit: ack path ───────────────────────────────────────
    # Hoisted above perm checks so ack/all paths don't trip on the
    # original "iterate ``ids`` and 404" loop (``ids`` is None on ack).
    if accept is not None and idempotency_key is not None:
        if not accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await restore_artifacts(
                        conn,
                        table="auth_artifact",
                        ids=ids or [idempotency_key],
                    )
        await refresh_auth_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )
        try:
            await perform_keycloak_sync(department_id=None)
        except Exception:
            pass
        return DeleteAuthApiResponse(
            results=[
                DeleteAuthResult(
                    success=True,
                    auth_id=auth_id,
                    message="Delete confirmed" if accept else "Delete rejected — auth restored",
                )
                for auth_id in (ids or [idempotency_key])
            ],
            idempotency_key=idempotency_key,
        )

    # ── All-matching path: resolve ids server-side ────────────────────
    if all:
        from app.infra.auth.resolve_matching_ids import resolve_matching_auth_ids
        matching = await resolve_matching_auth_ids(
            pool, redis,
            profile_id=profile_id,
            search=search,
            filter_department_ids=filter_department_ids,
            department_search=department_search,
            flag_search=flag_search,
        )
        excluded = set(excluded_ids or [])
        ids = [aid for aid in matching if aid not in excluded]

    # ── First-call requirements ───────────────────────────────────────
    if not ids:
        if all:
            return DeleteAuthApiResponse(results=[], idempotency_key=idempotency_key)
        raise HTTPException(
            status_code=400,
            detail="`auth_ids` is required for first-call deletion "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with filter fields).",
        )

    # ── Profile context ───────────────────────────────────────────────
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

    # ── Per-item permission checks ────────────────────────────────────
    # Explicit-ids path fails fast (preserves existing 404/403 behavior).
    # All-matching path soft-skips: collects per-row results so the
    # toast can say "X deleted, Y skipped (no permission)" without
    # aborting rows the user CAN delete.
    skipped_results: list[DeleteAuthResult] = []
    permitted_ids: list[UUID] = []

    async with pool.acquire() as conn:
        for idx, auth_id in enumerate(ids):
            ctx = await resolve_auth_permissions_context(conn, auth_id)
            if not ctx.exists:
                if all:
                    skipped_results.append(DeleteAuthResult(
                        success=False, auth_id=auth_id,
                        message=f"Auth {auth_id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Auth {auth_id} not found.",
                )
            if not compute_can_delete(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
                active_settings_count=ctx.active_settings_count,
            ):
                if all:
                    skipped_results.append(DeleteAuthResult(
                        success=False, auth_id=auth_id,
                        message=f"No permission to delete auth {auth_id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this auth entry.",
                )
            permitted_ids.append(auth_id)

    if all:
        ids = permitted_ids
        if not ids:
            return DeleteAuthApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    # ── Fetch names for result messages ───────────────────────────────
    name_map: dict[UUID, str] = {}
    async with pool.acquire() as conn:
        artifacts = await get_auths(conn, ids, names=True)
        for artifact in artifacts:
            name = "Unknown"
            if artifact.name_ids:
                name_resources = await get_names(pool, artifact.name_ids, redis)
                if name_resources:
                    name = name_resources[0].name or "Unknown"
            name_map[artifact.id] = name

    # ── Single transaction — bulk delete ──────────────────────────────
    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await delete_auths(conn, ids, soft=soft)

    await refresh_auth_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=idempotency_key or (result.deleted_ids[0] if result.deleted_ids else None),
    )

    if not soft:
        try:
            await perform_keycloak_sync(department_id=None)
        except Exception:
            pass

    results = [
        DeleteAuthResult(
            success=True,
            auth_id=pid,
            message=(
                f"Auth '{name_map.get(pid, 'Unknown')}' deleted (pending confirmation)"
                if soft
                else f"Auth '{name_map.get(pid, 'Unknown')}' deleted successfully"
            ),
        )
        for pid in result.deleted_ids
    ]

    # All-matching path threads any soft-skipped rows back into the
    # response so the client can surface "X deleted, Y skipped" in
    # one go. Explicit-ids path's skipped_results is empty.
    return DeleteAuthApiResponse(
        results=results + skipped_results,
        idempotency_key=idempotency_key,
    )
