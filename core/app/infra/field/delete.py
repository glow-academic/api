"""Field delete logic — composable infra architecture.

Core delete function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. resolve_field_permissions_context — per-item exists, departments
  3. search_parameters — inline usage check (active_parameter_count)
  4. compute_can_delete — permission check
  5. delete_fields — bulk delete tool
  6. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.delete.delete_artifact import restore_artifacts
from app.infra.field.permissions import compute_can_delete
from app.infra.field.permissions_context import resolve_field_permissions_context
from app.infra.field.refresh import refresh_field_impl
from app.infra.field.types import (
    DeleteFieldApiResponse,
    DeleteFieldResult,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.artifacts.field.delete import delete_fields
from app.tools.artifacts.field.get import get_fields
from app.tools.artifacts.parameter.search import search_parameters
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.resources.names.get import get_names

ARTIFACT = "field"


async def _refresh_field_deletes(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None,
    operation_key: UUID | None,
    soft: bool = False,
) -> None:
    """Refresh field state using the canonical call shape when available."""

    try:
        await refresh_field_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=operation_key,
        )
    except TypeError as exc:
        if "unexpected keyword argument" not in str(exc):
            raise
        await refresh_field_impl(pool, redis, profile_id=profile_id)


async def delete_field_impl(
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
    parameter_ids: list[UUID] | None = None,
    persona_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    parameter_search: str | None = None,
    persona_search: str | None = None,
    department_search: str | None = None,
    flag_search: str | None = None,
) -> DeleteFieldApiResponse:
    """Field bulk delete using composable infra functions.

    Three call shapes:
      - First call (explicit): ``ids`` required.
      - First call (all-matching): ``all=true`` plus filter fields. The
        impl resolves matching ids via ``resolve_matching_field_ids``,
        subtracts ``excluded_ids``, then runs the existing per-row flow.
        Per-row permission failures soft-skip (returned in results)
        rather than aborting the whole call.
      - Ack call: ``idempotency_key`` + ``accept`` only — no ``ids``
        needed, the dormant deletion is located by the operation key.

    Flow (first call):
      1. (all-matching only) resolve_matching_field_ids → ids
      2. resolve_profile_identity_context → role
      3. Per-item: resolve_field_permissions_context → exists, departments
      4. Per-item: search_parameters → active_parameter_count (inline usage check)
      5. Per-item: compute_can_delete → permission check
         - Explicit path: fail fast (existing behavior)
         - All-matching path: soft-skip with per-row result
      6. Fetch names for result messages
      7. Single transaction: delete_fields → bulk delete
      8. canonical refresh
    """

    # ── All-matching path: resolve ids server-side ────────────────────
    # Ahead of any ``ids``-dependent work and ``all=true`` ⇒ enumerate
    # every field matching the filter, then subtract ``excluded_ids``.
    # The per-row permission check below filters out anything the user
    # can't delete (soft-skip, returned in results).
    if all:
        from app.infra.field.resolve_matching_ids import resolve_matching_field_ids
        matching = await resolve_matching_field_ids(
            pool, redis,
            profile_id=profile_id,
            search=search,
            parameter_ids=parameter_ids,
            persona_ids=persona_ids,
            filter_department_ids=filter_department_ids,
            parameter_search=parameter_search,
            persona_search=persona_search,
            department_search=department_search,
            flag_search=flag_search,
        )
        excluded = set(excluded_ids or [])
        ids = [fid for fid in matching if fid not in excluded]

    # -- Step 1: Profile context -----------------------------------------------

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

    # ── Short-circuit: ack path ───────────────────────────────────────
    # (Done before per-item work since ack doesn't need any ids work.)
    if accept is not None and idempotency_key is not None:
        with timed("ack"):
            async with pool.acquire() as conn:
                entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
            if entry is None or entry.status != "pending" or entry.operation != "delete":
                raise HTTPException(
                    status_code=404,
                    detail="No pending field delete for this call.",
                )
            target_id = entry.artifact_id

            if not accept:
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        await restore_artifacts(
                            conn, table="field_artifact", ids=[target_id],
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

        with timed("refresh"):
            await _refresh_field_deletes(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                operation_key=idempotency_key,
            )
        return DeleteFieldApiResponse(
            results=[
                DeleteFieldResult(
                    success=True,
                    field_id=target_id,
                    message=(
                        "Delete confirmed"
                        if accept
                        else "Delete rejected — field restored"
                    ),
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── First-call requirements ───────────────────────────────────────
    # Past the ack short-circuit ⇒ this is a first call. Under
    # ``all=true`` the resolver above populated ``ids`` (possibly empty
    # if no matches).
    if not ids:
        if all:
            # Empty matching set — return an empty results list rather
            # than 400. The user's intent ("delete all matching") is
            # well-formed; the universe just happens to be empty.
            return DeleteFieldApiResponse(
                results=[],
                idempotency_key=idempotency_key,
            )
        raise HTTPException(
            status_code=400,
            detail="`field_ids` is required for first-call deletion "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with filter fields).",
        )

    # -- Step 2+3+4: Per-item permission checks --------------------------------
    # Explicit-ids path fails fast (preserves existing 404/403 behavior).
    # All-matching path soft-skips: collects per-row results so the
    # toast can say "X deleted, Y skipped (no permission)" without
    # aborting rows the user CAN delete.
    skipped_results: list[DeleteFieldResult] = []
    permitted_ids: list[UUID] = []

    with timed("permissions"):
     async with pool.acquire() as conn:
        for idx, field_id in enumerate(ids):
            ctx = await resolve_field_permissions_context(conn, field_id)

            if not ctx.exists:
                if all:
                    skipped_results.append(DeleteFieldResult(
                        success=False, field_id=field_id,
                        message=f"Field {field_id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Field {field_id} not found.",
                )

            # Field permissions context doesn't include active_parameter_count,
            # so we use search_parameters inline to check usage.
            active_parameter_ids, _total = await search_parameters(
                conn, field_ids=[field_id], active_only=True, limit_count=1
            )
            active_parameter_count = len(active_parameter_ids)

            if not compute_can_delete(
                role_level=profile.role_level, role_permissions=profile.role_permissions,
                field_department_ids=ctx.department_ids,
                active_parameter_count=active_parameter_count,
            ):
                if all:
                    skipped_results.append(DeleteFieldResult(
                        success=False, field_id=field_id,
                        message=f"No permission to delete field {field_id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this field.",
                )

            permitted_ids.append(field_id)

    # All-matching path: replace ``ids`` with the filtered set. Explicit
    # path leaves it alone (it already raised on any failure).
    if all:
        ids = permitted_ids
        if not ids:
            # Every matched row was skipped — return only the skipped
            # results. No actual delete fires.
            return DeleteFieldApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    # -- Step 5: Fetch names for result messages -------------------------------

    with timed("hydrate_names"):
     async with pool.acquire() as conn:
        name_map: dict[UUID, str] = {}
        artifacts = await get_fields(conn, ids, names=True)
        for artifact in artifacts:
            name = "Unknown"
            if artifact.name_ids:
                name_resources = await get_names(pool, artifact.name_ids, redis)
                if name_resources:
                    name = name_resources[0].name or "Unknown"
            name_map[artifact.id] = name

    # -- Step 6: Single transaction -- bulk delete -----------------------------

    with timed("db_write"):
     async with pool.acquire() as conn:
        async with conn.transaction():
            result = await delete_fields(conn, ids, soft=soft)

            # Pending ledger rows tied to this tool call.
            if soft and idempotency_key is not None:
                for fid in result.deleted_ids:
                    await create_soft_call(
                        conn,
                        redis,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="delete",
                        artifact_id=fid,
                    )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    # -- Step 7: Canonical refresh --------------------------------------------

    first_id = result.deleted_ids[0] if result.deleted_ids else None
    with timed("refresh"):
        await _refresh_field_deletes(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key or first_id,
            soft=soft,
        )

    results = [
        DeleteFieldResult(
            success=True,
            field_id=pid,
            message=(
                f"Field '{name_map.get(pid, 'Unknown')}' deleted (pending confirmation)"
                if soft
                else f"Field '{name_map.get(pid, 'Unknown')}' deleted successfully"
            ),
        )
        for pid in result.deleted_ids
    ]

    # All-matching path threads any soft-skipped rows back into the
    # response so the client can surface "X deleted, Y skipped" in
    # one go. Explicit-ids path's skipped_results is empty.
    return DeleteFieldApiResponse(
        results=results + skipped_results,
        idempotency_key=idempotency_key,
    )
