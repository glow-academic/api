"""Agent update logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. resolve_agent_permissions_context — per-item access + edit check
  3. resolve_agent_values — raw value → ID resolution
  4. update_agent_artifact — junction writes (partial update)
  5. create_denormalized_snapshot — agents_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.agent.permissions_context import (
    create_denormalized_snapshot,
    resolve_agent_permissions_context,
    resolve_agent_values,
)
from app.infra.agent.refresh import refresh_agent_impl
from app.infra.agent.types import UpdateAgentApiRequest, UpdateAgentApiResponse
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.artifacts.agent.update import (
    _UNSET,
)
from app.tools.artifacts.agent.update import (
    update_agent as update_agent_artifact,
)
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.utils.cache.hedged_row import transaction_with_writeback

ARTIFACT = "agent"


async def update_agent_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdateAgentApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdateAgentApiResponse:
    """Agent bulk update using composable infra functions.

    Three call shapes:
      - First call (explicit): ``request.agents`` required.
      - First call (all-matching): ``request.all=true`` plus ``patch``
        plus filter fields. The impl resolves matching ids, clones
        the patch per id (stamping each id), then runs the existing
        per-row update flow. Per-row permission failures soft-skip.
      - Ack call: ``idempotency_key`` + ``accept`` only.

    Flow (first call):
      1. (all-matching only) resolve_matching_agent_ids → synth items
      2. resolve_profile_identity_context → role, department_ids
      3. Per-item: resolve_agent_permissions_context → exists + compute_can_edit
      4. Per-item value resolution (raw → ID, no required field enforcement)
      5. Single transaction: update_agent_artifact + denormalized snapshot per item
      6. invalidate_tags
    """
    from app.infra.agent.permissions import (
        compute_can_edit,
        has_access,
    )
    from app.infra.agent.types import (
        AgentResultItem,
    )

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key and accept is None:
        accept = request.accept

    # ── Short-circuit: ack path ───────────────────────────────────────
    # Hoisted above permission checks: ack calls don't carry per-row
    # items (and previously the impl ran per-item perm checks against
    # a presumed ``items`` list, which fails when the ack path passes
    # an empty/None agents list — same hoist scenario does for persona).
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "update":
            raise HTTPException(
                status_code=404,
                detail="No pending agent update for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                async with transaction_with_writeback(conn):
                    await update_agent_artifact(conn, target_id, soft=False)

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                redis,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation="update",
                artifact_id=target_id,
                status="accepted" if accept else "rejected",
            )
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

        await refresh_agent_impl(
            pool, redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )
        return UpdateAgentApiResponse(
            results=[
                AgentResultItem(
                    success=True,
                    agent_id=target_id,
                    message="Update accepted" if accept else "Update rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── All-matching path: resolve ids + synthesize per-row items ─────
    # Past the ack short-circuit and ``all=true`` ⇒ enumerate every
    # agent matching the filter, then clone ``request.patch`` per
    # id (stamping the resolved id). The downstream per-row flow runs
    # unchanged. Per-row permission failures soft-skip (collected into
    # ``skipped_results`` and threaded into the final response).
    skipped_results: list[AgentResultItem] = []

    if request.all:
        if request.patch is None:
            raise HTTPException(
                status_code=400,
                detail="`patch` is required when `all=true` "
                "(it carries the shared change set applied to every matched row).",
            )
        from app.infra.agent.resolve_matching_ids import resolve_matching_agent_ids
        from app.infra.agent.types import UpdateAgentItem

        matching = await resolve_matching_agent_ids(
            pool, redis,
            profile_id=profile_id,
            search=request.search,
            filter_department_ids=request.filter_department_ids,
            filter_model_ids=request.filter_model_ids,
            filter_tool_ids=request.filter_tool_ids,
            department_search=request.department_search,
            model_search=request.model_search,
            tool_search=request.tool_search,
            flag_search=request.flag_search,
        )
        excluded = set(request.excluded_ids or [])
        resolved_ids = [aid for aid in matching if aid not in excluded]

        if not resolved_ids:
            # Empty matching set — well-formed intent, just no rows.
            return UpdateAgentApiResponse(results=[], idempotency_key=idempotency_key)

        # Clone the patch per matched row, stamping the resolved id.
        # ``model_dump(exclude_unset=True, exclude={"id"})`` keeps sparse
        # semantics — only fields the client actually set are written.
        patch_fields = request.patch.model_dump(exclude_unset=True, exclude={"id"})
        synth_items = [UpdateAgentItem(id=aid, **patch_fields) for aid in resolved_ids]
        # Splice into the request shape downstream code expects.
        request = request.model_copy(update={"agents": synth_items})

    # ── First-call requirements ───────────────────────────────────────
    if not request.agents:
        raise HTTPException(
            status_code=400,
            detail="`request.agents` is required for first-call update "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with `patch` and filter fields).",
        )

    items = request.agents

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

    # ── Step 2: Per-item permission check ──────────────────────────────
    # Explicit path fails fast (existing behavior).
    # All-matching path soft-skips so the response carries per-row
    # outcomes without aborting rows the user CAN edit.
    is_all_matching = bool(request.all)
    permitted_items: list = []

    with timed("permissions"):
     async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            perms = await resolve_agent_permissions_context(conn, item.id)
            if not perms.exists:
                if is_all_matching:
                    skipped_results.append(AgentResultItem(
                        success=False, agent_id=item.id,
                        message=f"Agent {item.id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Agent {item.id} not found.",
                )
            has_agent_access = has_access(
                profile.role_level, profile.department_ids, perms.department_ids
            )
            if not compute_can_edit(
                role_level=profile.role_level, role_permissions=profile.role_permissions,
                has_agent_access=has_agent_access,
                missing_tools=[],
                agent_id=item.id,
            ):
                if is_all_matching:
                    skipped_results.append(AgentResultItem(
                        success=False, agent_id=item.id,
                        message=f"No permission to update agent {item.id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this agent.",
                )

            permitted_items.append(item)

    if is_all_matching:
        items = permitted_items
        if not items:
            return UpdateAgentApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[AgentResultItem] = []

    with timed("resolve_values"):
     async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_agent_values(conn, redis, item, is_create=False)
            if item_errors:
                has_errors = True
                error_results.append(
                    AgentResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(AgentResultItem(success=True, message="Validated"))

    if has_errors:
        return UpdateAgentApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[AgentResultItem] = []

    with timed("db_write"):
     for item in items:
        agents_resource_id = None
        if not soft:
            agents_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                model_id=item.model_id,
                rubric_id=item.rubric_ids[0] if item.rubric_ids else None,
                tool_ids=item.tool_ids,
                voice_ids=item.voice_ids,
                prompt_id=item.prompt_id,
                instruction_ids=item.instruction_ids,
            )

        # Artifact update inside transaction
        async with pool.acquire() as conn:
            async with transaction_with_writeback(conn):
                combined_flag_ids = list(item.flag_ids or [])

                await update_agent_artifact(
                    conn,
                    item.id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id
                    if item.description_id
                    else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=combined_flag_ids or None,
                    model_ids=[item.model_id] if item.model_id else None,
                    reasoning_level_ids=item.reasoning_level_ids,
                    temperature_level_ids=item.temperature_level_ids,
                    tool_ids=item.tool_ids,
                    voice_ids=item.voice_ids,
                    agent_ids=[agents_resource_id],
                    rubric_ids=item.rubric_ids,
                    prompt_ids=[item.prompt_id] if item.prompt_id else None,
                    quality_ids=item.quality_ids,
                    soft=soft,
                )

                # Pending ledger row tied to this tool call (see create.py).
                if soft and idempotency_key is not None:
                    await create_soft_call(
                        conn,
                        redis,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="update",
                        artifact_id=item.id,
                    )

        results.append(
            AgentResultItem(
                success=True,
                agent_id=item.id,
                message=(
                    "Agent update accepted"
                    if accept is not None and idempotency_key is not None
                    else "Agent updated (pending acceptance)"
                    if soft
                    else "Agent updated successfully"
                ),
            )
        )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    if not soft:
        with timed("refresh"):
            await refresh_agent_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                soft=soft,
                operation_key=idempotency_key or (results[0].agent_id if results else None),
            )

    # All-matching path threads soft-skipped rows back into the
    # response so the client can surface "X updated, Y skipped" in
    # one toast. Explicit path's ``skipped_results`` is empty.
    return UpdateAgentApiResponse(
        results=results + skipped_results,
        idempotency_key=idempotency_key,
    )
