"""Persona delete logic — composable infra architecture.

Core delete function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. resolve_persona_permissions_context — per-item exists, departments, usage
  3. compute_can_delete — permission check
  4. delete_personas — bulk delete tool
  5. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.delete.delete_artifact import restore_artifacts
from app.infra.persona.permissions import compute_can_delete
from app.infra.persona.permissions_context import resolve_persona_permissions_context
from app.infra.persona.refresh import refresh_persona_impl
from app.infra.server_timing import timed
from app.infra.persona.types import (
    DeletePersonaApiResponse,
    DeletePersonaResult,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.persona.delete import delete_personas
from app.tools.artifacts.persona.get import get_personas
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.resources.names.get import get_names
from app.utils.cache.invalidate_tags import invalidate_tags

ARTIFACT = "persona"


async def delete_persona_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    ids: list[UUID] | None = None,
    session_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    # All-matching path (additive — explicit-ids path stays untouched).
    all: bool = False,
    excluded_ids: list[UUID] | None = None,
    search: str | None = None,
    scenario_ids: list[UUID] | None = None,
    field_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    scenario_search: str | None = None,
    field_search: str | None = None,
    department_search: str | None = None,
    color_search: str | None = None,
    icon_search: str | None = None,
    voice_search: str | None = None,
    instruction_search: str | None = None,
) -> DeletePersonaApiResponse:
    """Persona bulk delete using composable infra functions.

    Three call shapes:
      - First call (explicit): ``ids`` required.
      - First call (all-matching): ``all=true`` plus filter fields. The
        impl resolves matching ids via ``resolve_matching_persona_ids``,
        subtracts ``excluded_ids``, then runs the existing per-row flow.
        Per-row permission failures soft-skip (returned in results)
        rather than aborting the whole call.
      - Ack call: ``idempotency_key`` + ``accept`` only — no ``ids``
        needed, the dormant deletion is located by the operation key.

    Flow (first call):
      1. (all-matching only) resolve_matching_persona_ids → ids
      2. resolve_profile_identity_context → role
      3. Per-item: resolve_persona_permissions_context → exists, departments, usage
      4. Per-item: compute_can_delete → permission check
         - Explicit path: fail fast (existing behavior)
         - All-matching path: soft-skip with per-row result
      5. Fetch names for result messages
      6. Single transaction: delete_personas → bulk delete
      7. invalidate_tags
    """

    # ── Short-circuit: ack path ───────────────────────────────────────
    # ``idempotency_key`` is the originating tool call's ``calls_entry.id``.
    # Look up the ledger to resolve which persona was soft-deleted.
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "delete":
            raise HTTPException(
                status_code=404,
                detail="No pending persona delete for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            # Confirm deletion: no-op (already deactivated by soft delete).
            pass
        else:
            # Reject: restore the soft-deleted artifact.
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await restore_artifacts(
                        conn, table="persona_artifact", ids=[target_id],
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
        await refresh_persona_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            targets=["personas_mv", "soft_calls_mv"],
        )
        return DeletePersonaApiResponse(results=[
            DeletePersonaResult(
                success=True,
                id=target_id,
                message="Delete confirmed" if accept else "Delete rejected — persona restored",
            )
        ])

    # ── All-matching path: resolve ids server-side ────────────────────
    # Past the ack short-circuit and ``all=true`` ⇒ enumerate every
    # persona matching the filter, then subtract ``excluded_ids``.
    # The per-row permission check below filters out anything the
    # user can't delete (soft-skip, returned in results).
    if all:
        from app.infra.persona.resolve_matching_ids import resolve_matching_persona_ids
        matching = await resolve_matching_persona_ids(
            pool, redis,
            profile_id=profile_id,
            search=search,
            scenario_ids=scenario_ids,
            field_ids=field_ids,
            filter_department_ids=filter_department_ids,
            scenario_search=scenario_search,
            field_search=field_search,
            department_search=department_search,
            color_search=color_search,
            icon_search=icon_search,
            voice_search=voice_search,
            instruction_search=instruction_search,
        )
        excluded = set(excluded_ids or [])
        ids = [pid for pid in matching if pid not in excluded]

    # ── First-call requirements ───────────────────────────────────────
    # Past the ack short-circuit ⇒ this is a first call. ``ids`` is the
    # domain-specific requirement; the ack path located the dormant row
    # by ``idempotency_key`` and didn't need it. Under ``all=true`` the
    # resolver above populated ``ids`` (possibly empty if no matches).
    if not ids:
        if all:
            # Empty matching set — return an empty results list rather
            # than 400. The user's intent ("delete all matching") is
            # well-formed; the universe just happens to be empty.
            return DeletePersonaApiResponse(results=[])
        raise HTTPException(
            status_code=400,
            detail="`ids` is required for first-call deletion "
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
    skipped_results: list[DeletePersonaResult] = []
    permitted_ids: list[UUID] = []

    with timed("permissions"):
        for idx, persona_id in enumerate(ids):
            ctx = await resolve_persona_permissions_context(pool, persona_id)

            if not ctx.exists:
                if all:
                    skipped_results.append(DeletePersonaResult(
                        success=False, id=persona_id,
                        message=f"Persona {persona_id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Persona {persona_id} not found.",
                )

            if not compute_can_delete(
                role_level=profile.role_level, role_permissions=profile.role_permissions,
                persona_department_ids=ctx.department_ids,
                active_scenario_count=ctx.active_scenario_count,
            ):
                if all:
                    skipped_results.append(DeletePersonaResult(
                        success=False, id=persona_id,
                        message=f"No permission to delete persona {persona_id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this persona.",
                )

            permitted_ids.append(persona_id)

    # All-matching path: replace ``ids`` with the filtered set. Explicit
    # path leaves it alone (it already raised on any failure).
    if all:
        ids = permitted_ids
        if not ids:
            # Every matched row was skipped — return only the skipped
            # results. No actual delete fires.
            return DeletePersonaApiResponse(results=skipped_results)

    # ── Step 4: Fetch names for result messages ───────────────────────

    name_map: dict[UUID, str] = {}
    with timed("hydrate_names"):
        async with pool.acquire() as conn:
            artifacts = await get_personas(conn, ids, names=True)
            for artifact in artifacts:
                name = "Unknown"
                if artifact.name_ids:
                    name_resources = await get_names(pool, artifact.name_ids, redis)
                    if name_resources:
                        name = name_resources[0].name or "Unknown"
                name_map[artifact.id] = name

    # ── Step 5: Single transaction — bulk delete ──────────────────────

    with timed("db_write"):
        async with pool.acquire() as conn:
            async with conn.transaction():
                result = await delete_personas(conn, ids, soft=soft)

                # Soft delete: append a pending ledger row per id so ack
                # lookups can resolve which persona to restore on reject.
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

    # Refresh + invalidate (via canonical refresh)
    with timed("refresh"):
        await refresh_persona_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            targets=["personas_mv", "soft_calls_mv"],
        )

    results = [
        DeletePersonaResult(
            success=True,
            id=pid,
            message=f"Persona '{name_map.get(pid, 'Unknown')}' deleted (pending confirmation)" if soft
            else f"Persona '{name_map.get(pid, 'Unknown')}' deleted successfully",
        )
        for pid in result.deleted_ids
    ]

    # All-matching path threads any soft-skipped rows back into the
    # response so the client can surface "X deleted, Y skipped" in
    # one go. Explicit-ids path's skipped_results is empty.
    return DeletePersonaApiResponse(results=results + skipped_results)
