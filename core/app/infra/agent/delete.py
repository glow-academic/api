"""Agent delete logic — composable infra architecture.

Core delete function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. Per-item loop: permissions context + inline SQL for active_settings_count
  3. compute_can_delete — permission check
  4. delete_agents — bulk delete tool
  5. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.agent.permissions import compute_can_delete
from app.infra.agent.permissions_context import resolve_agent_permissions_context
from app.infra.agent.refresh import refresh_agent_impl
from app.infra.agent.types import (
    DeleteAgentApiResponse,
    DeleteAgentResult,
)
from app.infra.delete.delete_artifact import restore_artifacts
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.artifacts.agent.delete import delete_agents
from app.tools.artifacts.agent.get import get_agents
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.resources.names.get import get_names
from app.utils.cache.hedged_row import transaction_with_writeback

ARTIFACT = "agent"


async def delete_agent_impl(
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
    filter_tool_ids: list[UUID] | None = None,
    department_search: str | None = None,
    model_search: str | None = None,
    tool_search: str | None = None,
    flag_search: str | None = None,
) -> DeleteAgentApiResponse:
    """Agent bulk delete using composable infra functions.

    Three call shapes:
      - First call (explicit): ``ids`` required.
      - First call (all-matching): ``all=true`` plus filter fields. The
        impl resolves matching ids via ``resolve_matching_agent_ids``,
        subtracts ``excluded_ids``, then runs the existing per-row flow.
        Per-row permission failures soft-skip (returned in results)
        rather than aborting the whole call.
      - Ack call: ``idempotency_key`` + ``accept`` only — no ``ids``
        needed, the dormant deletion is located by the operation key.

    Flow (first call):
      1. (all-matching only) resolve_matching_agent_ids -> ids
      2. resolve_profile_identity_context -> role
      3. Per-item: resolve_agent_permissions_context -> exists, departments
      4. Per-item: inline SQL for active_settings_count
      5. Per-item: compute_can_delete -> permission check
         - Explicit path: fail fast (existing behavior)
         - All-matching path: soft-skip with per-row result
      6. Fetch names for result messages
      7. Single transaction: delete_agents -> bulk delete
      8. invalidate_tags
    """

    # ── Short-circuit: ack path ───────────────────────────────────────
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "delete":
            raise HTTPException(
                status_code=404,
                detail="No pending agent delete for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            # Confirm deletion: no-op (already deactivated by soft delete).
            pass
        else:
            # Reject: restore the soft-deleted artifact.
            async with pool.acquire() as conn:
                async with transaction_with_writeback(conn):
                    await restore_artifacts(
                        conn, table="agent_artifact", ids=[target_id],
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

        await refresh_agent_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )
        return DeleteAgentApiResponse(
            results=[
                DeleteAgentResult(
                    success=True,
                    agent_id=target_id,
                    message="Delete confirmed" if accept else "Delete rejected — agent restored",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── All-matching path: resolve ids server-side ────────────────────
    # Past the ack short-circuit and ``all=true`` ⇒ enumerate every
    # agent matching the filter, then subtract ``excluded_ids``.
    # The per-row permission check below filters out anything the
    # user can't delete (soft-skip, returned in results).
    if all:
        from app.infra.agent.resolve_matching_ids import resolve_matching_agent_ids
        matching = await resolve_matching_agent_ids(
            pool, redis,
            profile_id=profile_id,
            search=search,
            filter_department_ids=filter_department_ids,
            filter_model_ids=filter_model_ids,
            filter_tool_ids=filter_tool_ids,
            department_search=department_search,
            model_search=model_search,
            tool_search=tool_search,
            flag_search=flag_search,
        )
        excluded = set(excluded_ids or [])
        ids = [aid for aid in matching if aid not in excluded]

    # ── First-call requirements ───────────────────────────────────────
    if not ids:
        if all:
            # Empty matching set — return an empty results list rather
            # than 400. The user's intent ("delete all matching") is
            # well-formed; the universe just happens to be empty.
            return DeleteAgentApiResponse(results=[], idempotency_key=idempotency_key)
        raise HTTPException(
            status_code=400,
            detail="`agent_ids` is required for first-call deletion "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with filter fields).",
        )

    # -- Step 1: Profile context ------------------------------------------------

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

    # -- Step 2+3: Per-item permission checks -----------------------------------
    # Explicit-ids path fails fast (preserves existing 404/403 behavior).
    # All-matching path soft-skips: collects per-row results so the
    # toast can say "X deleted, Y skipped (no permission)" without
    # aborting rows the user CAN delete.
    skipped_results: list[DeleteAgentResult] = []
    permitted_ids: list[UUID] = []

    with timed("permissions"):
     async with pool.acquire() as conn:
        for idx, agent_id in enumerate(ids):
            ctx = await resolve_agent_permissions_context(conn, agent_id)

            if not ctx.exists:
                if all:
                    skipped_results.append(DeleteAgentResult(
                        success=False, agent_id=agent_id,
                        message=f"Agent {agent_id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Agent {agent_id} not found.",
                )

            # Active settings count via runs_agents_connection through agent_agents_junction
            active_settings_count: int = await conn.fetchval(
                """
                SELECT COUNT(DISTINCT rac.run_id)::int
                FROM agent_agents_junction aaj
                JOIN runs_agents_connection rac ON rac.agents_id = aaj.agents_id AND rac.active = true
                WHERE aaj.agent_id = $1 AND aaj.active = true
                """,
                agent_id,
            )

            if not compute_can_delete(
                role_level=profile.role_level, role_permissions=profile.role_permissions,
                active_settings_count=active_settings_count or 0,
                agent_department_ids=ctx.department_ids,
                user_department_ids=profile.department_ids,
            ):
                if all:
                    skipped_results.append(DeleteAgentResult(
                        success=False, agent_id=agent_id,
                        message=f"No permission to delete agent {agent_id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this agent.",
                )

            permitted_ids.append(agent_id)

    # All-matching path: replace ``ids`` with the filtered set. Explicit
    # path leaves it alone (it already raised on any failure).
    if all:
        ids = permitted_ids
        if not ids:
            # Every matched row was skipped — return only the skipped
            # results. No actual delete fires.
            return DeleteAgentApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    # -- Step 4: Fetch names for result messages --------------------------------

    with timed("names"):
     async with pool.acquire() as conn:
        name_map: dict[UUID, str] = {}
        artifacts = await get_agents(conn, ids, names=True)
        for artifact in artifacts:
            name = "Unknown"
            if artifact.name_ids:
                name_resources = await get_names(pool, artifact.name_ids, redis)
                if name_resources:
                    name = name_resources[0].name or "Unknown"
            name_map[artifact.id] = name

    # -- Step 5: Single transaction -- bulk delete ------------------------------

    with timed("db_write"):
     async with pool.acquire() as conn:
        async with transaction_with_writeback(conn):
            result = await delete_agents(conn, ids, soft=soft)

            # Soft delete: append a pending ledger row per id so ack
            # lookups can resolve which agent to restore on reject.
            if soft and idempotency_key is not None:
                for aid in result.deleted_ids:
                    await create_soft_call(
                        conn,
                        redis,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="delete",
                        artifact_id=aid,
                    )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    with timed("refresh"):
        await refresh_agent_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (result.deleted_ids[0] if result.deleted_ids else None),
        )

    results = [
        DeleteAgentResult(
            success=True,
            agent_id=pid,
            message=(
                f"Agent '{name_map.get(pid, 'Unknown')}' deleted (pending confirmation)"
                if soft
                else f"Agent '{name_map.get(pid, 'Unknown')}' deleted successfully"
            ),
        )
        for pid in result.deleted_ids
    ]

    # All-matching path threads any soft-skipped rows back into the
    # response so the client can surface "X deleted, Y skipped" in
    # one go. Explicit-ids path's skipped_results is empty.
    return DeleteAgentApiResponse(
        results=results + skipped_results,
        idempotency_key=idempotency_key,
    )
