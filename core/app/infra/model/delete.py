"""Model delete logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.delete.delete_artifact import restore_artifacts
from app.infra.model.permissions import compute_can_delete
from app.infra.model.permissions_context import resolve_model_permissions_context
from app.infra.model.refresh import refresh_model_impl
from app.infra.model.types import (
    DeleteModelApiResponse,
    DeleteModelResult,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.model.delete import delete_models
from app.tools.artifacts.model.get import get_models
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.resources.names.get import get_names

ARTIFACT = "model"


async def delete_model_impl(
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
    filter_provider_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    filter_agent_ids: list[UUID] | None = None,
    provider_search: str | None = None,
    department_search: str | None = None,
    agent_search: str | None = None,
    flag_search: str | None = None,
) -> DeleteModelApiResponse:
    """Model bulk delete using composable infra functions.

    Three call shapes:
      - First call (explicit): ``ids`` required.
      - First call (all-matching): ``all=true`` plus filter fields. The
        impl resolves matching ids via ``resolve_matching_model_ids``,
        subtracts ``excluded_ids``, then runs the existing per-row flow.
        Per-row permission failures soft-skip (returned in results)
        rather than aborting the whole call.
      - Ack call: ``idempotency_key`` + ``accept`` only — no ``ids``
        needed, the dormant deletion is located by the operation key.
    """

    # ── Short-circuit: ack path ───────────────────────────────────────
    # Ack-hoisted ABOVE perm checks because under the ack path
    # ``ids`` is None and the dormant row is located solely by
    # ``idempotency_key``. The original impl ran perm checks first,
    # which broke the ack path; mirror persona/scenario shape now.
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "delete":
            raise HTTPException(
                status_code=404,
                detail="No pending model delete for this call.",
            )
        target_id = entry.artifact_id

        if not accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await restore_artifacts(
                        conn, table="model_artifact", ids=[target_id],
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

        await refresh_model_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )
        return DeleteModelApiResponse(
            results=[
                DeleteModelResult(
                    success=True,
                    model_id=target_id,
                    message="Delete confirmed" if accept else "Delete rejected — model restored",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── All-matching path: resolve ids server-side ────────────────────
    # Past the ack short-circuit and ``all=true`` ⇒ enumerate every
    # model matching the filter, then subtract ``excluded_ids``. The
    # per-row permission check below filters out anything the user
    # can't delete (soft-skip, returned in results).
    if all:
        from app.infra.model.resolve_matching_ids import resolve_matching_model_ids
        matching = await resolve_matching_model_ids(
            pool, redis,
            profile_id=profile_id,
            search=search,
            filter_provider_ids=filter_provider_ids,
            filter_department_ids=filter_department_ids,
            filter_agent_ids=filter_agent_ids,
            provider_search=provider_search,
            department_search=department_search,
            agent_search=agent_search,
            flag_search=flag_search,
        )
        excluded = set(excluded_ids or [])
        ids = [mid for mid in matching if mid not in excluded]

    # ── First-call requirements ───────────────────────────────────────
    if not ids:
        if all:
            return DeleteModelApiResponse(results=[], idempotency_key=idempotency_key)
        raise HTTPException(
            status_code=400,
            detail="`model_ids` is required for first-call deletion "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with filter fields).",
        )

    # ── Profile context ──────────────────────────────────────────────
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

    # ── Per-item permission checks ───────────────────────────────────
    # Explicit-ids path fails fast (preserves existing 404/403 behavior).
    # All-matching path soft-skips: collects per-row results so the
    # toast can say "X deleted, Y skipped (no permission)" without
    # aborting rows the user CAN delete.
    skipped_results: list[DeleteModelResult] = []
    permitted_ids: list[UUID] = []

    async with pool.acquire() as conn:
        for idx, model_id in enumerate(ids):
            ctx = await resolve_model_permissions_context(conn, model_id)
            if not ctx.exists:
                if all:
                    skipped_results.append(DeleteModelResult(
                        success=False, model_id=model_id,
                        message=f"Model {model_id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Model {model_id} not found.",
                )
            if not compute_can_delete(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
                model_department_ids=ctx.department_ids,
                active_agent_count=ctx.active_agent_count,
            ):
                if all:
                    skipped_results.append(DeleteModelResult(
                        success=False, model_id=model_id,
                        message=f"No permission to delete model {model_id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this model.",
                )
            permitted_ids.append(model_id)

    if all:
        ids = permitted_ids
        if not ids:
            return DeleteModelApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    async with pool.acquire() as conn:
        name_map: dict[UUID, str] = {}
        artifacts = await get_models(conn, ids, names=True)
        for artifact in artifacts:
            name = "Unknown"
            if artifact.name_ids:
                name_resources = await get_names(pool, artifact.name_ids, redis)
                if name_resources:
                    name = name_resources[0].name or "Unknown"
            name_map[artifact.id] = name

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await delete_models(conn, ids, soft=soft)

            # Pending ledger rows tied to this tool call.
            if soft and idempotency_key is not None:
                for mid in result.deleted_ids:
                    await create_soft_call(
                        conn,
                        redis,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="delete",
                        artifact_id=mid,
                    )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    await refresh_model_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=idempotency_key or (result.deleted_ids[0] if result.deleted_ids else None),
    )

    results = [
        DeleteModelResult(
            success=True,
            model_id=pid,
            message=(
                f"Model '{name_map.get(pid, 'Unknown')}' deleted (pending confirmation)"
                if soft
                else f"Model '{name_map.get(pid, 'Unknown')}' deleted successfully"
            ),
        )
        for pid in result.deleted_ids
    ]

    # All-matching path threads any soft-skipped rows back into the
    # response so the client can surface "X deleted, Y skipped" in
    # one go. Explicit-ids path's skipped_results is empty.
    return DeleteModelApiResponse(
        results=results + skipped_results,
        idempotency_key=idempotency_key,
    )
