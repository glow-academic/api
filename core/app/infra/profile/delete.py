"""Profile delete logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.delete.delete_artifact import restore_artifacts
from app.infra.profile.permissions import compute_can_delete
from app.infra.profile.permissions_context import resolve_profile_permissions_context
from app.infra.profile.refresh import refresh_profile_impl
from app.infra.profile.types import (
    DeleteProfileApiResponse,
    DeleteProfileResult,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.artifacts.profile.delete import delete_profiles
from app.tools.artifacts.profile.get import get_profiles
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.resources.names.get import get_names

ARTIFACT = "profile"


async def delete_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    profile_ids: list[UUID] | None = None,
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    # All-matching path (additive — explicit-ids path stays untouched).
    all: bool = False,
    excluded_ids: list[UUID] | None = None,
    search: str | None = None,
    cohort_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    role_filter: str | None = None,
    cohort_search: str | None = None,
    department_search: str | None = None,
    role_search: str | None = None,
    flag_search: str | None = None,
) -> DeleteProfileApiResponse:
    """Profile bulk delete using composable infra functions.

    Three call shapes:
      - First call (explicit): ``profile_ids`` required.
      - First call (all-matching): ``all=true`` plus filter fields. The
        impl resolves matching ids via ``resolve_matching_profile_ids``,
        subtracts ``excluded_ids``, then runs the existing per-row flow.
        Per-row permission failures soft-skip (returned in results)
        rather than aborting the whole call.
      - Ack call: ``idempotency_key`` + ``accept`` only — no ``profile_ids``
        needed, the dormant deletion is located by the operation key.
    """

    # ── Short-circuit: ack path ───────────────────────────────────────
    # Hoisted above the per-row permission loop because under ack and
    # all-matching paths ``profile_ids`` is None on entry; running the
    # loop first would either raise or silently skip checks. Persona's
    # canonical pattern.
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "delete":
            raise HTTPException(
                status_code=404,
                detail="No pending profile delete for this call.",
            )
        target_id = entry.artifact_id

        if not accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await restore_artifacts(
                        conn,
                        table="profile_artifact",
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
            ],
            idempotency_key=idempotency_key,
        )

    # ── All-matching path: resolve ids server-side ────────────────────
    # Past the ack short-circuit and ``all=true`` ⇒ enumerate every
    # profile matching the filter, then subtract ``excluded_ids``.
    # The per-row permission check below filters out anything the
    # user can't delete (soft-skip, returned in results).
    if all:
        from app.infra.profile.resolve_matching_ids import resolve_matching_profile_ids
        matching = await resolve_matching_profile_ids(
            pool, redis,
            profile_id=profile_id,
            search=search,
            cohort_ids=cohort_ids,
            filter_department_ids=filter_department_ids,
            role_filter=role_filter,
            cohort_search=cohort_search,
            department_search=department_search,
            role_search=role_search,
            flag_search=flag_search,
        )
        excluded = set(excluded_ids or [])
        profile_ids = [pid for pid in matching if pid not in excluded]

    # ── First-call requirements ───────────────────────────────────────
    if not profile_ids:
        if all:
            # Empty matching set — return an empty results list rather
            # than 400. The user's intent ("delete all matching") is
            # well-formed; the universe just happens to be empty.
            return DeleteProfileApiResponse(results=[], idempotency_key=idempotency_key)
        raise HTTPException(
            status_code=400,
            detail="`profile_ids` is required for first-call deletion "
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
    skipped_results: list[DeleteProfileResult] = []
    permitted_ids: list[UUID] = []

    with timed("permissions"):
      async with pool.acquire() as conn:
        for idx, target_id in enumerate(profile_ids):
            ctx = await resolve_profile_permissions_context(conn, target_id)

            if not ctx.exists:
                if all:
                    skipped_results.append(DeleteProfileResult(
                        success=False, profile_id=target_id,
                        message=f"Profile {target_id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Profile {target_id} not found.",
                )

            target_ctx = await resolve_profile_identity_context(pool, target_id, redis)
            target_level = target_ctx.role_level if target_ctx else None

            if not compute_can_delete(
                role_level=profile.role_level, role_permissions=profile.role_permissions,
                target_is_self=(target_id == profile_id),
                target_level=target_level,
            ):
                if all:
                    skipped_results.append(DeleteProfileResult(
                        success=False, profile_id=target_id,
                        message=f"No permission to delete profile {target_id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this profile.",
                )

            permitted_ids.append(target_id)

    # All-matching path: replace ``profile_ids`` with the filtered set.
    # Explicit path leaves it alone (it already raised on any failure).
    if all:
        profile_ids = permitted_ids
        if not profile_ids:
            return DeleteProfileApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    with timed("hydrate"):
      async with pool.acquire() as conn:
        name_map: dict[UUID, str] = {}
        artifacts = await get_profiles(conn, profile_ids, names=True)
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
            result = await delete_profiles(conn, profile_ids, soft=soft)

            if soft and idempotency_key is not None:
                for pid in result.deleted_ids:
                    await create_soft_call(
                        conn,
                        redis,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="delete",
                        artifact_id=pid,
                    )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    with timed("refresh"):
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

    # All-matching path threads any soft-skipped rows back into the
    # response so the client can surface "X deleted, Y skipped" in
    # one go. Explicit-ids path's skipped_results is empty.
    return DeleteProfileApiResponse(
        results=results + skipped_results,
        idempotency_key=idempotency_key,
    )
