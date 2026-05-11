"""Rubric update logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.rubric.permissions_context import (
    create_denormalized_snapshot,
    resolve_rubric_permissions_context,
    resolve_rubric_point_totals,
    resolve_rubric_values,
)
from app.infra.rubric.refresh import refresh_rubric_impl
from app.infra.rubric.types import (
    UpdateRubricApiRequest,
    UpdateRubricApiResponse,
    UpdateRubricItem,
)
from app.tools.artifacts.rubric.update import (
    _UNSET,
)
from app.tools.artifacts.rubric.update import (
    update_rubric as update_rubric_artifact,
)
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls

ARTIFACT = "rubric"


async def update_rubric_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdateRubricApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdateRubricApiResponse:
    """Rubric bulk update using composable infra functions.

    Three call shapes:
      - First call (explicit): ``request.rubrics`` required.
      - First call (all-matching): ``request.all=true`` plus ``patch``
        plus filter fields. The impl resolves matching ids, clones
        the patch per id (stamping each id), then runs the existing
        per-row update flow. Per-row permission failures soft-skip.
      - Ack call: ``idempotency_key`` + ``accept`` only.
    """
    from app.infra.rubric.permissions import compute_can_edit
    from app.infra.rubric.types import RubricResultItem

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    # ── Short-circuit: ack path ───────────────────────────────────────
    # Hoisted above per-row perm checks so ack/all paths don't need
    # ``request.rubrics``. Under ack=False we just echo a "rejected"
    # result; under ack=True the soft-update junctions are already
    # active (existing semantics), we just refresh caches.
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "update":
            raise HTTPException(
                status_code=404,
                detail="No pending rubric update for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await update_rubric_artifact(
                        conn,
                        target_id,
                        soft=False,
                    )

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation="update",
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

        from app.infra.rubric.hydrate_list_rows import hydrate_rubric_list_rows
        hydrated_rows = await hydrate_rubric_list_rows(
            pool, redis, profile_id=profile_id, rubric_ids=[target_id],
        )
        return UpdateRubricApiResponse(
            results=[
                RubricResultItem(
                    success=True,
                    rubric_id=target_id,
                    message="Update accepted" if accept else "Update rejected",
                )
            ],
            rubrics=hydrated_rows,
            idempotency_key=idempotency_key,
        )

    # ── All-matching path: resolve ids + synthesize per-row items ─────
    skipped_results: list[RubricResultItem] = []

    if request.all:
        if request.patch is None:
            raise HTTPException(
                status_code=400,
                detail="`patch` is required when `all=true` "
                "(it carries the shared change set applied to every matched row).",
            )
        from app.infra.rubric.resolve_matching_ids import resolve_matching_rubric_ids
        from app.infra.rubric.types import UpdateRubricItem

        matching = await resolve_matching_rubric_ids(
            pool, redis,
            profile_id=profile_id,
            search=request.search,
            filter_department_ids=request.filter_department_ids,
            filter_simulation_ids=request.filter_simulation_ids,
            department_search=request.department_search,
            simulation_search=request.simulation_search,
            flag_search=request.flag_search,
        )
        excluded = set(request.excluded_ids or [])
        resolved_ids = [rid for rid in matching if rid not in excluded]

        if not resolved_ids:
            return UpdateRubricApiResponse(
                results=[],
                idempotency_key=idempotency_key,
            )

        # Clone the patch per matched row, stamping the resolved id.
        # ``model_dump(exclude_unset=True, exclude={"id"})`` keeps sparse
        # semantics — only fields the client actually set are written.
        patch_fields = request.patch.model_dump(exclude_unset=True, exclude={"id"})
        synth_items = [UpdateRubricItem(id=rid, **patch_fields) for rid in resolved_ids]
        request = request.model_copy(update={"rubrics": synth_items})

    # ── First-call requirements ───────────────────────────────────────
    if not request.rubrics:
        raise HTTPException(
            status_code=400,
            detail="`request.rubrics` is required for first-call update "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with `patch` and filter fields).",
        )

    items = request.rubrics

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

    # ── Per-item permission check ─────────────────────────────────────
    # Explicit path fails fast (existing behavior).
    # All-matching path soft-skips so the response carries per-row
    # outcomes without aborting rows the user CAN edit.
    is_all_matching = bool(request.all)
    permitted_items: list = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            perms = await resolve_rubric_permissions_context(conn, item.id)
            if not perms.exists:
                if is_all_matching:
                    skipped_results.append(RubricResultItem(
                        success=False, rubric_id=item.id,
                        message=f"Rubric {item.id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Rubric {item.id} not found.",
                )
            if not compute_can_edit(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
                rubric_department_ids=perms.department_ids,
                active_simulation_count=perms.active_simulation_count,
            ):
                if is_all_matching:
                    skipped_results.append(RubricResultItem(
                        success=False, rubric_id=item.id,
                        message=f"No permission to update rubric {item.id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this rubric.",
                )
            permitted_items.append(item)

    if is_all_matching:
        items = permitted_items
        if not items:
            return UpdateRubricApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    has_errors = False
    error_results: list[RubricResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_rubric_values(conn, redis, item, is_create=False)
            if item_errors:
                has_errors = True
                error_results.append(
                    RubricResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(RubricResultItem(success=True, message="Validated"))

    if has_errors:
        return UpdateRubricApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    results: list[RubricResultItem] = []

    # Denormalize point values (pass from id, max from standard groups) and
    # per-type bools from flag_ids for the snapshot.
    from app.tools.resources.flags.search import search_flags

    async def _flag_bools_by_type(item: UpdateRubricItem) -> dict[str, bool]:
        if not item.flag_ids:
            return {}
        async with pool.acquire() as conn:
            flag_rows = await search_flags(
                conn, redis, search=None, limit_count=1000, bypass_cache=True,
            )
        rows_by_id = {row.id: row for row in flag_rows if getattr(row, "id", None)}
        out: dict[str, bool] = {}
        for fid in item.flag_ids:
            row = rows_by_id.get(fid)
            if not row:
                continue
            rtype = getattr(row, "type", None) or getattr(row, "name", None)
            rval = getattr(row, "value", None)
            if rtype and rval is not None:
                out[rtype] = bool(rval)
        return out

    for item in items:
        pass_value, total_value = await resolve_rubric_point_totals(
            pool,
            redis,
            pass_points_id=item.pass_points_id,
            standard_group_ids=item.standard_group_ids,
            standard_ids=item.standard_ids,
        )

        rubrics_resource_id = None
        if not soft:
            flag_bools = await _flag_bools_by_type(item)
            rubrics_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                standard_group_ids=item.standard_group_ids,
                simulation_rubric=flag_bools.get("simulation_rubric", False),
                video_rubric=flag_bools.get("video_rubric", False),
                total_points=total_value,
                pass_points=pass_value,
            )

        point_ids = [item.pass_points_id] if item.pass_points_id else None

        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_rubric_artifact(
                    conn,
                    item.id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id if item.description_id else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=item.flag_ids or None,
                    point_ids=point_ids,
                    standard_group_ids=item.standard_group_ids,
                    standard_ids=item.standard_ids,
                    rubric_ids=[rubrics_resource_id] if rubrics_resource_id else None,
                    soft=soft,
                )

                if soft and idempotency_key is not None:
                    await create_soft_call(
                        conn,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="update",
                        artifact_id=item.id,
                    )

        results.append(
            RubricResultItem(
                success=True,
                rubric_id=item.id,
                message=(
                    "Rubric updated (pending acceptance)"
                    if soft
                    else "Rubric updated successfully"
                ),
            )
        )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    if not soft:
        await refresh_rubric_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (results[0].rubric_id if results else None),
        )

    # Hydrate the updated rows so the client's ghost rail can refresh
    # the changed cards without a ``router.refresh()``. Skipped on soft
    # writes (the change isn't promoted until ack-accept).
    hydrated_rows = None
    if not soft:
        from app.infra.rubric.hydrate_list_rows import hydrate_rubric_list_rows

        updated_ids = [r.rubric_id for r in results if r.success and r.rubric_id]
        if updated_ids:
            hydrated_rows = await hydrate_rubric_list_rows(
                pool, redis, profile_id=profile_id, rubric_ids=updated_ids,
            )

    # All-matching path threads soft-skipped rows back into the
    # response so the client can surface "X updated, Y skipped" in
    # one toast. Explicit path's ``skipped_results`` is empty.
    return UpdateRubricApiResponse(
        results=results + skipped_results,
        rubrics=hydrated_rows,
        idempotency_key=idempotency_key,
    )
