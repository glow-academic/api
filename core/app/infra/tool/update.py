"""Tool update logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. resolve_tool_permissions_context — per-item access + edit check
  3. resolve_tool_values — raw value → ID resolution
  4. update_tool_artifact — junction writes (partial update)
  5. create_denormalized_snapshot — tools_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.tool.hydrate_list_rows import hydrate_tool_list_rows
from app.infra.server_timing import timed
from app.infra.tool.permissions_context import (
    create_denormalized_snapshot,
    resolve_tool_permissions_context,
    resolve_tool_values,
)
from app.infra.tool.refresh import refresh_tool_impl
from app.infra.tool.types import (
    UpdateToolApiRequest,
    UpdateToolApiResponse,
)
from app.tools.artifacts.tool.update import (
    _UNSET,
)
from app.tools.artifacts.tool.update import (
    update_tool as update_tool_artifact,
)
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls

ARTIFACT = "tool"


async def update_tool_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdateToolApiRequest | None = None,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdateToolApiResponse:
    """Tool bulk update using composable infra functions.

    Three call shapes:
      - First call (explicit): ``request.tools`` required.
      - First call (all-matching): ``request.all=true`` plus the filter
        fields ``/tool/search`` accepts plus a single shared ``patch``.
        The impl resolves matching ids, subtracts ``excluded_ids``, and
        runs the existing per-row update flow with the patch cloned per
        id. Per-row permission failures soft-skip.
      - Ack call: ``idempotency_key`` + ``accept`` only — the dormant
        update is located by the operation key.

    Flow (first call):
      1. resolve_profile_identity_context → role
      2. (all-matching only) resolve_matching_tool_ids → synthesize items
      3. Per-item: resolve_tool_permissions_context → exists + compute_can_edit
      4. Per-item value resolution (raw → ID, no required field enforcement)
      5. Single transaction: update_tool_artifact + denormalized snapshot per item
      6. canonical refresh
    """
    from app.infra.tool.permissions import compute_can_edit
    from app.infra.tool.types import (
        ToolResultItem,
    )

    # ── Merge ack fields from request ─────────────────────────────────
    if request is not None:
        idempotency_key = idempotency_key or request.idempotency_key
        if idempotency_key and accept is None:
            accept = request.accept

    # ── Short-circuit: ack path ───────────────────────────────────────
    # Hoisted above per-row perm checks: under ack, ``request.tools`` is
    # None (the dormant artifact is located by ``idempotency_key``) so
    # the previous "perm-loop first" ordering broke on this shape.
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "update":
            raise HTTPException(
                status_code=404,
                detail="No pending tool update for this call.",
            )
        target_id = entry.artifact_id

        if not accept:
            async with pool.acquire() as conn:
                await create_soft_call(
                    conn,
                    redis,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation="update",
                    artifact_id=target_id,
                    status="rejected",
                )
            async with pool.acquire() as conn:
                await refresh_soft_calls(conn)
            return UpdateToolApiResponse(
                results=[
                    ToolResultItem(
                        success=True,
                        tool_id=target_id,
                        message="Update rejected",
                    )
                ],
                idempotency_key=idempotency_key,
            )

        # Promote dormant update — fall through to the normal flow with
        # ``soft=False``; the rest of the impl handles the confirm.
        # (Mirrors persona's promote semantics.)
        soft = False

    # ── All-matching path: resolve ids + synthesize per-row items ─────
    # Past the ack short-circuit and ``all=true`` ⇒ enumerate every
    # tool matching the filter, then clone ``request.patch`` per id
    # (stamping the resolved id). The downstream per-row flow runs
    # unchanged. Per-row permission failures soft-skip (collected into
    # ``skipped_results`` and threaded into the final response).
    skipped_results: list[ToolResultItem] = []

    if request is not None and request.all:
        if request.patch is None:
            raise HTTPException(
                status_code=400,
                detail="`patch` is required when `all=true` "
                "(it carries the shared change set applied to every matched row).",
            )
        from app.infra.tool.resolve_matching_ids import resolve_matching_tool_ids
        from app.infra.tool.types import UpdateToolItem

        matching = await resolve_matching_tool_ids(
            pool, redis,
            profile_id=profile_id,
            search=request.search,
            filter_department_ids=request.filter_department_ids,
            filter_creatable=request.filter_creatable,
            filter_agent_ids=request.filter_agent_ids,
            department_search=request.department_search,
            flag_search=request.flag_search,
            agent_search=request.agent_search,
        )
        excluded = set(request.excluded_ids or [])
        resolved_ids = [tid for tid in matching if tid not in excluded]

        if not resolved_ids:
            # Empty matching set — well-formed intent, just no rows.
            return UpdateToolApiResponse(results=[], idempotency_key=idempotency_key)

        # Clone the patch per matched row, stamping the resolved id.
        # ``model_dump(exclude_unset=True, exclude={"id"})`` keeps sparse
        # semantics — only fields the client actually set are written.
        patch_fields = request.patch.model_dump(exclude_unset=True, exclude={"id"})
        synth_items = [UpdateToolItem(id=tid, **patch_fields) for tid in resolved_ids]
        # Splice into the request shape downstream code expects.
        request = request.model_copy(update={"tools": synth_items})

    # ── First-call requirements ───────────────────────────────────────
    if request is None or not request.tools:
        raise HTTPException(
            status_code=400,
            detail="`request.tools` is required for first-call update "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with `patch` and filter fields).",
        )

    items = request.tools

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
    is_all_matching = request is not None and bool(request.all)
    permitted_items: list = []

    with timed("permissions"):
      async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            perms = await resolve_tool_permissions_context(conn, item.id)
            if not perms.exists:
                if is_all_matching:
                    skipped_results.append(ToolResultItem(
                        success=False, tool_id=item.id,
                        message=f"Tool {item.id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Tool {item.id} not found.",
                )
            if not compute_can_edit(
                role_level=profile.role_level, role_permissions=profile.role_permissions,
                active_agent_count=perms.active_agent_count,
            ):
                if is_all_matching:
                    skipped_results.append(ToolResultItem(
                        success=False, tool_id=item.id,
                        message=f"No permission to update tool {item.id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this tool.",
                )

            permitted_items.append(item)

    # All-matching path: filter ``items`` to permitted rows only. The
    # explicit path leaves it untouched (it already raised on any
    # failure).
    if is_all_matching:
        items = permitted_items
        if not items:
            return UpdateToolApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[ToolResultItem] = []

    with timed("resolve_values"):
      async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_tool_values(conn, redis, item, is_create=False)
            if item_errors:
                has_errors = True
                error_results.append(
                    ToolResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(ToolResultItem(success=True, message="Validated"))

    if has_errors:
        return UpdateToolApiResponse(results=error_results, idempotency_key=idempotency_key)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[ToolResultItem] = []

    with timed("db_write"):
     for item in items:
        # Create denormalized snapshot OUTSIDE transaction (skip when soft).
        tools_resource_id = None
        if not soft:
            tools_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                args_ids=item.args_ids,
                args_output_ids=item.args_outputs_ids,
                permission_ids=item.permission_ids,
                instruction_id=item.instruction_id,
            )

        combined_flag_ids = list(item.flag_ids or [])

        # Artifact update inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_tool_artifact(
                    conn,
                    item.id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id
                    if item.description_id
                    else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=combined_flag_ids or None,
                    arg_positions_ids=item.arg_positions_ids,
                    args_ids=item.args_ids,
                    args_outputs_ids=item.args_outputs_ids,
                    permission_ids=item.permission_ids,
                    instruction_ids=[item.instruction_id]
                    if item.instruction_id
                    else None,
                    tool_ids=[tools_resource_id] if tools_resource_id else None,
                    soft=soft,
                )

                if soft and idempotency_key is not None:
                    await create_soft_call(
                        conn,
                        redis,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="update",
                        artifact_id=item.id,
                    )
                elif accept is True and idempotency_key is not None:
                    await create_soft_call(
                        conn,
                        redis,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="update",
                        artifact_id=item.id,
                        status="accepted",
                    )

        results.append(
            ToolResultItem(
                success=True,
                tool_id=item.id,
                message=(
                    "Tool update accepted"
                    if accept is not None and idempotency_key is not None
                    else "Tool updated (pending acceptance)"
                    if soft
                    else "Tool updated successfully"
                ),
            )
        )

    # ── Step 4b: Refresh soft_calls_mv after pending ledger row insert ─

    if (soft or accept is True) and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    # ── Step 5: Refresh via canonical helper ────────────────────────────

    if not soft:
        with timed("refresh"):
            await refresh_tool_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                soft=soft,
                operation_key=idempotency_key or (results[0].tool_id if results else None),
            )

    # ── Step 6: Hydrate updated rows for the client's ghost rail ───────
    # Skip on soft writes — the dormant update isn't visible until the
    # ack-accept path promotes it.
    hydrated_tools: list | None = None
    if not soft:
        with timed("hydrate"):
            updated_ids = [r.tool_id for r in results if r.tool_id is not None]
            if updated_ids:
                hydrated_tools = await hydrate_tool_list_rows(
                    pool, redis, profile_id=profile_id, tool_ids=updated_ids,
                )

    # All-matching path threads soft-skipped rows back into the
    # response so the client can surface "X updated, Y skipped" in one
    # toast. Explicit path's ``skipped_results`` is empty.
    return UpdateToolApiResponse(
        results=results + skipped_results,
        idempotency_key=idempotency_key,
        tools=hydrated_tools,
    )
