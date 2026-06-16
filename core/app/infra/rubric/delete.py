"""Rubric delete logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.delete.delete_artifact import restore_artifacts
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.rubric.permissions import compute_can_delete
from app.infra.rubric.permissions_context import resolve_rubric_permissions_context
from app.infra.server_timing import timed
from app.infra.rubric.refresh import refresh_rubric_impl
from app.infra.rubric.types import (
    DeleteRubricApiResponse,
    DeleteRubricResult,
)
from app.tools.artifacts.rubric.delete import delete_rubrics
from app.tools.artifacts.rubric.get import get_rubrics
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.resources.names.get import get_names
from app.utils.cache.hedged_row import transaction_with_writeback

ARTIFACT = "rubric"


async def delete_rubric_impl(
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
    filter_simulation_ids: list[UUID] | None = None,
    department_search: str | None = None,
    simulation_search: str | None = None,
    flag_search: str | None = None,
) -> DeleteRubricApiResponse:
    """Rubric bulk delete using composable infra functions.

    Three call shapes:
      - First call (explicit): ``ids`` required.
      - First call (all-matching): ``all=true`` plus filter fields. The
        impl resolves matching ids via ``resolve_matching_rubric_ids``,
        subtracts ``excluded_ids``, then runs the existing per-row flow.
        Per-row permission failures soft-skip (returned in results)
        rather than aborting the whole call.
      - Ack call: ``idempotency_key`` + ``accept`` only — no ``ids``
        needed, the dormant deletion is located by the operation key.
    """
    # ── Short-circuit: ack path ───────────────────────────────────────
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "delete":
            raise HTTPException(
                status_code=404,
                detail="No pending rubric delete for this call.",
            )
        target_id = entry.artifact_id

        if not accept:
            async with pool.acquire() as conn:
                async with transaction_with_writeback(conn):
                    await restore_artifacts(
                        conn,
                        table="rubric_artifact",
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

        await refresh_rubric_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )
        return DeleteRubricApiResponse(
            results=[
                DeleteRubricResult(
                    success=True,
                    rubric_id=target_id,
                    message="Delete confirmed" if accept else "Delete rejected — rubric restored",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── All-matching path: resolve ids server-side ────────────────────
    if all:
        from app.infra.rubric.resolve_matching_ids import resolve_matching_rubric_ids
        matching = await resolve_matching_rubric_ids(
            pool, redis,
            profile_id=profile_id,
            search=search,
            filter_department_ids=filter_department_ids,
            filter_simulation_ids=filter_simulation_ids,
            department_search=department_search,
            simulation_search=simulation_search,
            flag_search=flag_search,
        )
        excluded = set(excluded_ids or [])
        ids = [rid for rid in matching if rid not in excluded]

    # ── First-call requirements ───────────────────────────────────────
    if not ids:
        if all:
            # Empty matching set — well-formed intent, just no rows.
            return DeleteRubricApiResponse(results=[], idempotency_key=idempotency_key)
        raise HTTPException(
            status_code=400,
            detail="`rubric_ids` is required for first-call deletion "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with filter fields).",
        )

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

    # ── Per-item permission checks ────────────────────────────────────
    # Explicit-ids path fails fast (preserves existing 404/403 behavior).
    # All-matching path soft-skips: collects per-row results so the
    # toast can say "X deleted, Y skipped (no permission)" without
    # aborting rows the user CAN delete.
    skipped_results: list[DeleteRubricResult] = []
    permitted_ids: list[UUID] = []

    with timed("permissions"):
      async with pool.acquire() as conn:
        for idx, rubric_id in enumerate(ids):
            ctx = await resolve_rubric_permissions_context(conn, rubric_id)
            if not ctx.exists:
                if all:
                    skipped_results.append(DeleteRubricResult(
                        success=False, rubric_id=rubric_id,
                        message=f"Rubric {rubric_id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Rubric {rubric_id} not found.",
                )
            if not compute_can_delete(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
                rubric_department_ids=ctx.department_ids,
                user_department_ids=profile.department_ids,
                active_simulation_count=ctx.active_simulation_count,
            ):
                if all:
                    skipped_results.append(DeleteRubricResult(
                        success=False, rubric_id=rubric_id,
                        message=f"No permission to delete rubric {rubric_id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this rubric.",
                )
            permitted_ids.append(rubric_id)

    if all:
        ids = permitted_ids
        if not ids:
            # Every matched row was skipped — return only the skipped
            # results. No actual delete fires.
            return DeleteRubricApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    with timed("hydrate_names"):
      async with pool.acquire() as conn:
        name_map: dict[UUID, str] = {}
        artifacts = await get_rubrics(conn, ids, names=True)
        for artifact in artifacts:
            name = "Unknown"
            if artifact.name_ids:
                name_resources = await get_names(pool, artifact.name_ids, redis)
                if name_resources:
                    name = name_resources[0].name or "Unknown"
            name_map[artifact.id] = name

    with timed("db_write"):
      async with pool.acquire() as conn:
        async with transaction_with_writeback(conn):
            result = await delete_rubrics(conn, ids, soft=soft)

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
        await refresh_rubric_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (result.deleted_ids[0] if result.deleted_ids else None),
        )

    results = [
        DeleteRubricResult(
            success=True,
            rubric_id=pid,
            message=(
                f"Rubric '{name_map.get(pid, 'Unknown')}' deleted (pending confirmation)"
                if soft
                else f"Rubric '{name_map.get(pid, 'Unknown')}' deleted successfully"
            ),
        )
        for pid in result.deleted_ids
    ]

    # All-matching path threads any soft-skipped rows back into the
    # response so the client can surface "X deleted, Y skipped" in
    # one go. Explicit-ids path's skipped_results is empty.
    return DeleteRubricApiResponse(
        results=results + skipped_results,
        idempotency_key=idempotency_key,
    )
