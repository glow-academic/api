"""Tool create logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. compute_can_create — permission check
  3. resolve_tool_values — raw value → ID resolution
  4. create_tool_artifact — junction writes
  5. create_denormalized_snapshot — tools_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.infra.tool.hydrate_list_rows import hydrate_tool_list_rows
from app.infra.tool.permissions_context import (
    create_denormalized_snapshot,
    resolve_tool_values,
)
from app.infra.tool.refresh import refresh_tool_impl
from app.infra.tool.types import (
    CreateToolApiRequest,
    CreateToolApiResponse,
    CreateToolItem,
    ToolFieldError,
    ToolResultItem,
)
from app.tools.artifacts.tool.create import (
    create_tool as create_tool_artifact,
)
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls

ARTIFACT = "tool"


async def _validate_tool_schema(
    conn: asyncpg.Connection,
    redis: Redis,
    item: CreateToolItem,
) -> list[str]:
    """Return human-readable warnings about a tool's declared args_outputs.

    Composes both structural checks via ``validate_tool_outputs``:

    * **unknown outputs** — names no permission's handler accepts (the LLM
      would set them and they'd drop on the floor).
    * **missing required** — required kwargs (intersection of required
      across permissions) that no declared output produces (handler would
      reject the call at runtime).
    * **partial-coverage declared** — declared fields only some permissions
      accept; legitimate for cross-cutting tools but worth surfacing.

    Best-effort, warn-mode: returns ``[]`` if the tool has no declared
    outputs, no declared permissions, or every permission's handler accepts
    ``**kwargs`` (nothing to validate against). Callers surface warnings
    without blocking the write — seed CI reuses this helper via the runner.
    """
    from app.infra.tool.canonical_signature import validate_tool_outputs
    from app.tools.resources.args_outputs.get import get_args_outputs
    from app.tools.resources.permissions.get import get_permissions

    output_ids = list(item.args_outputs_ids or [])
    perm_ids = list(item.permission_ids or [])
    if not output_ids or not perm_ids:
        return []

    args_outputs = await get_args_outputs(conn, output_ids, redis, bypass_cache=False)
    permissions = await get_permissions(conn, perm_ids, redis, bypass_cache=False)

    output_names = [ao.name for ao in args_outputs if ao.name]
    perm_pairs = [(p.artifact, p.operation) for p in permissions if p.artifact and p.operation]

    return validate_tool_outputs(perm_pairs, output_names).to_warnings()


async def create_tool_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: CreateToolApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> CreateToolApiResponse:
    """Tool bulk create using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role
      2. compute_can_create — single check (applies to all items)
      3. Per-item value resolution (raw → ID, required field enforcement)
      4. Single transaction: create_tool_artifact + denormalized snapshot per item
      5. canonical refresh
    """
    from app.infra.tool.permissions import compute_can_create

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    items = request.tools
    if idempotency_key is not None and len(items) == 1 and items[0].id is None:
        items = [items[0].model_copy(update={"id": idempotency_key})]

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

    # ── Step 2: Permission check ───────────────────────────────────────

    with timed("permissions"):
        if not compute_can_create(role_level=profile.role_level, role_permissions=profile.role_permissions):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to create tools.",
            )

    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "create":
            raise HTTPException(
                status_code=404,
                detail="No pending tool create for this call.",
            )
        target_id = entry.artifact_id

        if not accept:
            async with pool.acquire() as conn:
                await create_soft_call(
                    conn,
                    redis,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation="create",
                    artifact_id=target_id,
                    status="rejected",
                )
            async with pool.acquire() as conn:
                await refresh_soft_calls(conn)
            return CreateToolApiResponse(
                results=[
                    ToolResultItem(
                        success=True,
                        tool_id=target_id,
                        message="Tool rejected",
                    )
                ],
                idempotency_key=idempotency_key,
            )
        # accept=True: promote dormant via normal path with soft=False;
        # stamp target_id so the artifact id matches the dormant row.
        soft = False
        items = [items[0].model_copy(update={"id": target_id})] if items else items

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[ToolResultItem] = []

    with timed("resolve_values"):
      async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_tool_values(conn, redis, item, is_create=True)
            # Schema audit: derived surface from the selected permissions must
            # accept every declared args_output name. Warn-mode — we log but
            # don't block the create, so legitimate seeds with var_kwargs
            # handlers or in-progress tools still land. Seed CI separately
            # surfaces the count.
            schema_warnings = await _validate_tool_schema(conn, redis, item)
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
                msg = (
                    "Validated"
                    if not schema_warnings
                    else f"Validated (schema warnings: {schema_warnings})"
                )
                error_results.append(ToolResultItem(success=True, message=msg))

    if has_errors:
        return CreateToolApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    # ── Step 4: Denormalized snapshots (skip when soft — dormant artifact) ─

    results: list[ToolResultItem] = []
    snapshot_ids: list[UUID] = []

    if not soft:
      with timed("snapshot"):
        for item in items:
            tools_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                id=item.resource_id,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                args_ids=item.args_ids,
                args_output_ids=item.args_outputs_ids,
                permission_ids=item.permission_ids,
                instruction_id=item.instruction_id,
            )
            snapshot_ids.append(tools_resource_id)

    # ── Step 5: Single transaction — artifact writes ───────────────────

    with timed("db_write"):
      async with pool.acquire() as conn:
        async with conn.transaction():
            for idx, item in enumerate(items):
                combined_flag_ids = list(item.flag_ids or [])

                result = await create_tool_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=item.department_ids,
                    flag_ids=combined_flag_ids or None,
                    arg_positions_ids=item.arg_positions_ids,
                    args_ids=item.args_ids,
                    args_outputs_ids=item.args_outputs_ids,
                    permission_ids=item.permission_ids,
                    instruction_ids=[item.instruction_id]
                    if item.instruction_id
                    else None,
                    tool_ids=[snapshot_ids[idx]] if snapshot_ids else None,
                    soft=soft,
                )

                if soft and idempotency_key is not None:
                    await create_soft_call(
                        conn,
                        redis,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="create",
                        artifact_id=result.id,
                    )
                elif accept is True and idempotency_key is not None:
                    await create_soft_call(
                        conn,
                        redis,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="create",
                        artifact_id=result.id,
                        status="accepted",
                    )

                results.append(
                    ToolResultItem(
                        success=True,
                        tool_id=result.id,
                        message=(
                            "Tool accepted"
                            if accept is not None and idempotency_key is not None
                            else
                            "Tool created (pending acceptance)"
                            if soft
                            else "Tool created successfully"
                        ),
                    )
                )

    if (soft or accept is True) and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

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

    # ── Step 6: Hydrate created rows for the client's ghost rail ───────
    # Skip on soft writes — the dormant artifact isn't fully active until
    # the ack-accept path promotes it (which has its own flow).
    hydrated_tools: list | None = None
    if not soft:
        with timed("hydrate"):
            created_ids = [r.tool_id for r in results if r.tool_id is not None]
            if created_ids:
                hydrated_tools = await hydrate_tool_list_rows(
                    pool, redis, profile_id=profile_id, tool_ids=created_ids,
                )

    return CreateToolApiResponse(
        results=results,
        idempotency_key=idempotency_key,
        tools=hydrated_tools,
    )
