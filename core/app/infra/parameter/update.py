"""Parameter update logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. resolve_parameter_permissions_context — per-item access + edit check
  3. resolve_parameter_values — raw value → ID resolution
  4. update_parameter_artifact — junction writes (partial update)
  5. create_denormalized_snapshot — parameters_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.parameter.hydrate_list_rows import hydrate_parameter_list_rows
from app.infra.parameter.permissions_context import (
    create_denormalized_snapshot,
    resolve_parameter_permissions_context,
    resolve_parameter_values,
)
from app.infra.parameter.refresh import refresh_parameter_impl
from app.infra.parameter.types import (
    UpdateParameterApiRequest,
    UpdateParameterApiResponse,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.parameter.get import get_parameters as get_parameter_artifacts
from app.tools.artifacts.parameter.update import (
    _UNSET,
)
from app.tools.artifacts.parameter.update import (
    update_parameter as update_parameter_artifact,
)
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.resources.parameters.get import get_parameters as get_parameter_resources

ARTIFACT = "parameter"


async def update_parameter_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdateParameterApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdateParameterApiResponse:
    """Parameter bulk update using composable infra functions.

    Three call shapes:
      - First call (explicit): ``request.parameters`` required.
      - First call (all-matching): ``request.all=true`` plus ``patch``
        plus filter fields. The impl resolves matching ids, clones
        the patch per id (stamping each id), then runs the existing
        per-row update flow. Per-row permission failures soft-skip.
      - Ack call: ``idempotency_key`` + ``accept`` only.

    Flow (first call):
      1. (all-matching only) resolve_matching_parameter_ids → synth items
      2. resolve_profile_identity_context → role, department_ids
      3. Per-item: resolve_parameter_permissions_context → exists + compute_can_edit
      4. Per-item value resolution (raw → ID, no required field enforcement)
      5. Single transaction: update_parameter_artifact + denormalized snapshot per item
      6. canonical refresh via refresh_parameter_impl
    """
    from app.infra.parameter.permissions import compute_can_edit
    from app.infra.parameter.types import (
        ParameterResultItem,
    )

    # Merge ack fields from request (HTTP) or params (generation pipeline)
    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key and accept is None:
        accept = request.accept

    # ── Short-circuit: ack path ───────────────────────────────────────
    # Hoisted above per-row permission checks so the dormant promotion
    # path doesn't need ``request.parameters`` populated (matches
    # persona/scenario; see batch-1/2 lessons in
    # project_bulk_write_pattern.md).
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "update":
            raise HTTPException(
                status_code=404,
                detail="No pending parameter update for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await update_parameter_artifact(
                        conn,
                        target_id,
                        soft=False,
                    )

            async with pool.acquire() as conn:
                artifacts = await get_parameter_artifacts(
                    conn,
                    [target_id],
                    names=True,
                    descriptions=True,
                    departments=True,
                    flags=True,
                    fields=True,
                    parameters=True,
                )
                parameter_resources = await get_parameter_resources(
                    conn,
                    artifacts[0].parameter_ids[:1] if artifacts and artifacts[0].parameter_ids else [],
                    redis,
                    bypass_cache=True,
                )
            if artifacts:
                artifact = artifacts[0]
                parameter_resource = parameter_resources[0] if parameter_resources else None
                await create_denormalized_snapshot(
                    pool,
                    redis,
                    name_id=artifact.name_ids[0] if artifact.name_ids else None,
                    description_id=artifact.description_ids[0] if artifact.description_ids else None,
                    department_ids=artifact.department_ids,
                    field_ids=artifact.field_ids,
                    persona_parameter=parameter_resource.persona_parameter if parameter_resource else False,
                    document_parameter=parameter_resource.document_parameter if parameter_resource else False,
                    scenario_parameter=parameter_resource.scenario_parameter if parameter_resource else False,
                    video_parameter=parameter_resource.video_parameter if parameter_resource else False,
                )

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

        await refresh_parameter_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )

        return UpdateParameterApiResponse(
            results=[
                ParameterResultItem(
                    success=True,
                    parameter_id=target_id,
                    message="Update accepted" if accept else "Update rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── All-matching path: resolve ids + synthesize per-row items ─────
    # Past the ack short-circuit and ``all=true`` ⇒ enumerate every
    # parameter matching the filter, then clone ``request.patch`` per
    # id (stamping the resolved id). The downstream per-row flow runs
    # unchanged. Per-row permission failures soft-skip (collected into
    # ``skipped_results`` and threaded into the final response).
    skipped_results: list[ParameterResultItem] = []

    if request.all:
        if request.patch is None:
            raise HTTPException(
                status_code=400,
                detail="`patch` is required when `all=true` "
                "(it carries the shared change set applied to every matched row).",
            )
        from app.infra.parameter.resolve_matching_ids import (
            resolve_matching_parameter_ids,
        )
        from app.infra.parameter.types import UpdateParameterItem

        matching = await resolve_matching_parameter_ids(
            pool, redis,
            profile_id=profile_id,
            search=request.search,
            scenario_ids=request.scenario_ids,
            field_ids=request.field_ids,
            filter_department_ids=request.filter_department_ids,
            scenario_search=request.scenario_search,
            field_search=request.field_search,
            department_search=request.department_search,
            flag_search=request.flag_search,
        )
        excluded = set(request.excluded_ids or [])
        resolved_ids = [pid for pid in matching if pid not in excluded]

        if not resolved_ids:
            # Empty matching set — well-formed intent, just no rows.
            return UpdateParameterApiResponse(
                results=[],
                idempotency_key=idempotency_key,
            )

        # Clone the patch per matched row, stamping the resolved id.
        # ``model_dump(exclude_unset=True, exclude={"id"})`` keeps sparse
        # semantics — only fields the client actually set are written.
        patch_fields = request.patch.model_dump(exclude_unset=True, exclude={"id"})
        synth_items = [UpdateParameterItem(id=pid, **patch_fields) for pid in resolved_ids]
        # Splice into the request shape downstream code expects.
        request = request.model_copy(update={"parameters": synth_items})

    # ── First-call requirements ───────────────────────────────────────
    if not request.parameters:
        raise HTTPException(
            status_code=400,
            detail="`request.parameters` is required for first-call update "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with `patch` and filter fields).",
        )

    items = request.parameters

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

    # ── Step 2: Per-item permission check ──────────────────────────────
    # Explicit path fails fast (existing behavior).
    # All-matching path soft-skips so the response carries per-row
    # outcomes without aborting rows the user CAN edit.
    is_all_matching = bool(request.all)
    permitted_items: list = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            perms = await resolve_parameter_permissions_context(conn, item.id)
            if not perms.exists:
                if is_all_matching:
                    skipped_results.append(ParameterResultItem(
                        success=False, parameter_id=item.id,
                        message=f"Parameter {item.id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Parameter {item.id} not found.",
                )
            if not compute_can_edit(
                role_level=profile.role_level, role_permissions=profile.role_permissions,
                parameter_department_ids=perms.department_ids,
                active_scenario_count=perms.active_scenario_count,
                user_department_ids=profile.department_ids,
            ):
                if is_all_matching:
                    skipped_results.append(ParameterResultItem(
                        success=False, parameter_id=item.id,
                        message=f"No permission to update parameter {item.id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this parameter.",
                )

            permitted_items.append(item)

    if is_all_matching:
        items = permitted_items
        if not items:
            return UpdateParameterApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[ParameterResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_parameter_values(
                conn, redis, item, is_create=False
            )
            if item_errors:
                has_errors = True
                error_results.append(
                    ParameterResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(
                    ParameterResultItem(success=True, message="Validated")
                )

    if has_errors:
        return UpdateParameterApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[ParameterResultItem] = []

    for item in items:
        # Create denormalized snapshot only for the live path.
        parameters_resource_id = None
        if not soft:
            parameters_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                field_ids=item.field_ids,
            )

        # Artifact update inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_parameter_artifact(
                    conn,
                    item.id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id
                    if item.description_id
                    else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=item.flag_ids,
                    field_ids=item.field_ids,
                    parameter_ids=[parameters_resource_id],
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

        results.append(
            ParameterResultItem(
                success=True,
                parameter_id=item.id,
                message=(
                    "Parameter updated (pending acceptance)"
                    if soft
                    else "Parameter updated successfully"
                ),
            )
        )

    # ── Step 5: Canonical refresh ──────────────────────────────────────
    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    await refresh_parameter_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=idempotency_key or (results[0].parameter_id if results else None),
    )

    # ── Step 6: Hydrate list rows (skip soft) ─────────────────────────
    # Returns rows in the same shape as ``/parameter/search`` so the
    # client's ghost rail can patch in updated rows directly from the
    # audit ``.completed`` payload — no follow-up search burst.
    hydrated_rows = None
    if not soft:
        updated_ids = [r.parameter_id for r in results if r.success and r.parameter_id]
        if updated_ids:
            hydrated_rows = await hydrate_parameter_list_rows(
                pool, redis,
                profile_id=profile_id,
                parameter_ids=updated_ids,
            )

    # All-matching path threads soft-skipped rows back into the
    # response so the client can surface "X updated, Y skipped" in
    # one toast. Explicit path's ``skipped_results`` is empty.
    return UpdateParameterApiResponse(
        results=results + skipped_results,
        parameters=hydrated_rows,
        idempotency_key=idempotency_key,
    )
