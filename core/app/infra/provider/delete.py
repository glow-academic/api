"""Provider delete logic — composable infra architecture.

Core delete function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. resolve_provider_permissions_context — per-item exists, departments, usage
  3. compute_can_delete — permission check
  4. delete_providers — bulk delete tool
  5. canonical refresh
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.delete.delete_artifact import restore_artifacts
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.provider.permissions import compute_can_delete
from app.infra.provider.permissions_context import resolve_provider_permissions_context
from app.infra.provider.refresh import refresh_provider_impl
from app.infra.provider.types import (
    DeleteProviderApiResponse,
    DeleteProviderResult,
)
from app.tools.artifacts.provider.delete import delete_providers
from app.tools.artifacts.provider.get import get_providers
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.resources.names.get import get_names

ARTIFACT = "provider"


async def delete_provider_impl(
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
    filter_model_ids: list[UUID] | None = None,
    filter_status: list[str] | None = None,
    department_search: str | None = None,
    model_search: str | None = None,
    flag_search: str | None = None,
) -> DeleteProviderApiResponse:
    """Provider bulk delete using composable infra functions.

    Three call shapes:
      - First call (explicit): ``ids`` required.
      - First call (all-matching): ``all=true`` plus filter fields. The
        impl resolves matching ids via ``resolve_matching_provider_ids``,
        subtracts ``excluded_ids``, then runs the existing per-row flow.
        Per-row permission failures soft-skip (returned in results)
        rather than aborting the whole call.
      - Ack call: ``idempotency_key`` + ``accept`` only — no ``ids``
        needed, the dormant deletion is located by the operation key.

    Flow (first call):
      1. (all-matching only) resolve_matching_provider_ids → ids
      2. resolve_profile_identity_context → role
      3. Per-item: resolve_provider_permissions_context → exists, departments, usage
      4. Per-item: compute_can_delete → permission check
         - Explicit path: fail fast (existing behavior)
         - All-matching path: soft-skip with per-row result
      5. Fetch names for result messages
      6. Single transaction: delete_providers → bulk delete
      7. canonical refresh
    """

    # ── Short-circuit: ack path ───────────────────────────────────────
    # Hoisted above per-row perm checks because under ack/all paths
    # ``ids`` is None and the perm loop would explode. The dormant row
    # is located by ``idempotency_key`` — no per-row work needed.
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "delete":
            raise HTTPException(
                status_code=404,
                detail="No pending provider delete for this call.",
            )
        target_id = entry.artifact_id

        if not accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await restore_artifacts(
                        conn,
                        table="provider_artifact",
                        ids=[target_id],
                    )

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation="delete",
                artifact_id=target_id,
                status="accepted" if accept else "rejected",
            )
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

        await refresh_provider_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )
        return DeleteProviderApiResponse(
            results=[
                DeleteProviderResult(
                    success=True,
                    provider_id=target_id,
                    message=(
                        "Delete confirmed"
                        if accept
                        else "Delete rejected — provider restored"
                    ),
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── All-matching path: resolve ids server-side ────────────────────
    # Past the ack short-circuit and ``all=true`` ⇒ enumerate every
    # provider matching the filter, then subtract ``excluded_ids``.
    # The per-row permission check below filters out anything the
    # user can't delete (soft-skip, returned in results).
    if all:
        from app.infra.provider.resolve_matching_ids import (
            resolve_matching_provider_ids,
        )
        matching = await resolve_matching_provider_ids(
            pool, redis,
            profile_id=profile_id,
            search=search,
            filter_department_ids=filter_department_ids,
            filter_model_ids=filter_model_ids,
            filter_status=filter_status,
            department_search=department_search,
            model_search=model_search,
            flag_search=flag_search,
        )
        excluded = set(excluded_ids or [])
        ids = [pid for pid in matching if pid not in excluded]

    # ── First-call requirements ───────────────────────────────────────
    if not ids:
        if all:
            # Empty matching set — return an empty results list rather
            # than 400. The user's intent ("delete all matching") is
            # well-formed; the universe just happens to be empty.
            return DeleteProviderApiResponse(
                results=[], idempotency_key=idempotency_key,
            )
        raise HTTPException(
            status_code=400,
            detail="`provider_ids` is required for first-call deletion "
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
    skipped_results: list[DeleteProviderResult] = []
    permitted_ids: list[UUID] = []

    async with pool.acquire() as conn:
        for idx, provider_id in enumerate(ids):
            ctx = await resolve_provider_permissions_context(conn, provider_id)

            if not ctx.exists:
                if all:
                    skipped_results.append(DeleteProviderResult(
                        success=False, provider_id=provider_id,
                        message=f"Provider {provider_id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Provider {provider_id} not found.",
                )

            if not compute_can_delete(
                role_level=profile.role_level, role_permissions=profile.role_permissions,
                provider_department_ids=ctx.department_ids,
                active_model_count=ctx.active_model_count,
            ):
                if all:
                    skipped_results.append(DeleteProviderResult(
                        success=False, provider_id=provider_id,
                        message=f"No permission to delete provider {provider_id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this provider.",
                )

            permitted_ids.append(provider_id)

    # All-matching path: replace ``ids`` with the filtered set. Explicit
    # path leaves it alone (it already raised on any failure).
    if all:
        ids = permitted_ids
        if not ids:
            # Every matched row was skipped — return only the skipped
            # results. No actual delete fires.
            return DeleteProviderApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    # ── Step 4: Fetch names for result messages ───────────────────────

    async with pool.acquire() as conn:
        name_map: dict[UUID, str] = {}
        artifacts = await get_providers(conn, ids, names=True)
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
            result = await delete_providers(conn, ids, soft=soft)

            if soft and idempotency_key is not None:
                for pid in result.deleted_ids:
                    await create_soft_call(
                        conn,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="delete",
                        artifact_id=pid,
                    )

    # ── Step 6: Canonical refresh ─────────────────────────────────────
    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    await refresh_provider_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=idempotency_key or (result.deleted_ids[0] if result.deleted_ids else None),
    )

    results = [
        DeleteProviderResult(
            success=True,
            provider_id=pid,
            message=(
                f"Provider '{name_map.get(pid, 'Unknown')}' deleted (pending confirmation)"
                if soft
                else f"Provider '{name_map.get(pid, 'Unknown')}' deleted successfully"
            ),
        )
        for pid in result.deleted_ids
    ]

    # All-matching path threads any soft-skipped rows back into the
    # response so the client can surface "X deleted, Y skipped" in
    # one go. Explicit-ids path's skipped_results is empty.
    return DeleteProviderApiResponse(
        results=results + skipped_results,
        idempotency_key=idempotency_key,
    )
