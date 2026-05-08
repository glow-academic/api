"""Eval update logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.eval.permissions_context import (
    create_denormalized_snapshot,
    resolve_eval_permissions_context,
    resolve_eval_values,
)
from app.infra.eval.refresh import refresh_eval_impl
from app.infra.eval.types import UpdateEvalApiRequest, UpdateEvalApiResponse
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.eval.get import get_evals as get_eval_artifacts
from app.tools.artifacts.eval.update import _UNSET
from app.tools.artifacts.eval.update import update_eval as update_eval_artifact
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def update_eval_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdateEvalApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdateEvalApiResponse:
    """Eval bulk update using composable infra functions.

    Three call shapes:
      - First call (explicit): ``request.evals`` required.
      - First call (all-matching): ``request.all=true`` plus ``patch``
        and the same filter fields ``/eval/search`` accepts. The impl
        resolves matching ids, clones ``patch`` per id, and runs the
        existing per-row update flow. Per-row failures soft-skip.
      - Ack call: ``idempotency_key`` + ``accept`` only — the dormant
        update is located by the operation key.
    """
    from app.infra.eval.permissions import compute_can_edit
    from app.infra.eval.types import EvalResultItem

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    # ── Short-circuit: ack path ───────────────────────────────────────
    # Hoisted above per-row checks so the ack body (no ``evals``) doesn't
    # need to satisfy the existence/permission loop. The ack doesn't
    # know which rows were touched without a registry hop, so we just
    # echo the operation key back as a single result.
    if accept is not None and idempotency_key is not None:
        if not accept:
            return UpdateEvalApiResponse(
                results=[
                    EvalResultItem(
                        success=True,
                        eval_id=idempotency_key,
                        message="Update rejected",
                    )
                ],
                idempotency_key=idempotency_key,
            )
        soft = False
        # On accept the dormant write was already committed during
        # the original soft-update; nothing further to do here. Drop
        # through with empty items so we just echo a success result.
        if not request.evals and not request.all:
            return UpdateEvalApiResponse(
                results=[
                    EvalResultItem(
                        success=True,
                        eval_id=idempotency_key,
                        message="Update accepted",
                    )
                ],
                idempotency_key=idempotency_key,
            )

    # ── All-matching path: resolve ids + synthesize per-row items ─────
    # Past the ack short-circuit and ``all=true`` ⇒ enumerate every
    # eval matching the filter, then clone ``request.patch`` per id
    # (stamping the resolved id). Downstream per-row flow runs
    # unchanged. Per-row permission failures soft-skip.
    skipped_results: list[EvalResultItem] = []
    is_all_matching = bool(request.all)

    if is_all_matching:
        if request.patch is None:
            raise HTTPException(
                status_code=400,
                detail="`patch` is required when `all=true` "
                "(it carries the shared change set applied to every matched row).",
            )
        from app.infra.eval.resolve_matching_ids import resolve_matching_eval_ids
        from app.infra.eval.types import UpdateEvalItem

        matching = await resolve_matching_eval_ids(
            pool, redis,
            profile_id=profile_id,
            search=request.search,
            filter_department_ids=request.filter_department_ids,
            department_search=request.department_search,
            flag_search=request.flag_search,
        )
        excluded = set(request.excluded_ids or [])
        resolved_ids = [eid for eid in matching if eid not in excluded]

        if not resolved_ids:
            return UpdateEvalApiResponse(results=[], idempotency_key=idempotency_key)

        patch_fields = request.patch.model_dump(exclude_unset=True, exclude={"id"})
        synth_items = [UpdateEvalItem(id=eid, **patch_fields) for eid in resolved_ids]
        request = request.model_copy(update={"evals": synth_items})

    # ── First-call requirements ───────────────────────────────────────
    if not request.evals:
        raise HTTPException(
            status_code=400,
            detail="`evals` is required for first-call update "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with `patch` and filter fields).",
        )

    items = request.evals

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

    permitted_items: list = []
    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            perms = await resolve_eval_permissions_context(conn, item.id)
            if not perms.exists:
                if is_all_matching:
                    skipped_results.append(EvalResultItem(
                        success=False, eval_id=item.id,
                        message=f"Eval {item.id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Eval {item.id} not found.",
                )
            if not compute_can_edit(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
            ):
                if is_all_matching:
                    skipped_results.append(EvalResultItem(
                        success=False, eval_id=item.id,
                        message=f"No permission to update eval {item.id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this eval.",
                )
            permitted_items.append(item)

    if is_all_matching:
        items = permitted_items
        if not items:
            return UpdateEvalApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    has_errors = False
    error_results: list[EvalResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_eval_values(conn, redis, item, is_create=False)
            if item_errors:
                has_errors = True
                error_results.append(
                    EvalResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(EvalResultItem(success=True, message="Validated"))

    if has_errors:
        return UpdateEvalApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    results: list[EvalResultItem] = []
    sync_items: list[tuple[UUID, object]] = []

    for item in items:
        async with pool.acquire() as conn:
            existing = await get_eval_artifacts(
                conn,
                [item.id],
                names=True,
                descriptions=True,
                departments=True,
                models=True,
                model_flags=True,
                model_positions=True,
                model_rubrics=True,
            )

        evals_resource_id = None
        if not soft:
            if existing:
                artifact = existing[0]
                eff_name_id = item.name_id or (artifact.name_ids[0] if artifact.name_ids else None)
                eff_description_id = item.description_id or (artifact.description_ids[0] if artifact.description_ids else None)
                eff_department_ids = item.department_ids if item.department_ids is not None else list(artifact.department_ids or [])
                eff_model_ids = item.model_ids if item.model_ids is not None else list(artifact.model_ids or [])
                eff_model_flag_ids = item.model_flag_ids if item.model_flag_ids is not None else list(artifact.model_flag_ids or [])
                eff_model_position_ids = item.model_position_ids if item.model_position_ids is not None else list(artifact.model_position_ids or [])
                eff_model_rubric_ids = item.model_rubric_ids if item.model_rubric_ids is not None else list(artifact.model_rubric_ids or [])
            else:
                eff_name_id = item.name_id
                eff_description_id = item.description_id
                eff_department_ids = item.department_ids
                eff_model_ids = item.model_ids
                eff_model_flag_ids = item.model_flag_ids
                eff_model_position_ids = item.model_position_ids
                eff_model_rubric_ids = item.model_rubric_ids

            evals_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                name_id=eff_name_id,
                description_id=eff_description_id,
                department_ids=eff_department_ids,
                model_ids=eff_model_ids,
                model_rubric_ids=eff_model_rubric_ids,
                model_flag_ids=eff_model_flag_ids,
                model_position_ids=eff_model_position_ids,
            )
            sync_items.append((evals_resource_id, item))

        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_eval_artifact(
                    conn,
                    item.id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id if item.description_id else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=item.flag_ids or None,
                    model_ids=item.model_ids,
                    model_flag_ids=item.model_flag_ids,
                    model_rubric_ids=item.model_rubric_ids,
                    model_position_ids=item.model_position_ids,
                    eval_ids=[evals_resource_id] if evals_resource_id else None,
                    soft=soft,
                )

        results.append(
            EvalResultItem(
                success=True,
                eval_id=item.id,
                message=(
                    "Eval update accepted"
                    if accept is not None and idempotency_key is not None
                    else "Eval updated (pending acceptance)"
                    if soft
                    else "Eval updated successfully"
                ),
            )
        )

    if not soft:
        await refresh_eval_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (results[0].eval_id if results else None),
        )

        for resource_id, item in sync_items:
            try:
                from app.infra.benchmark.sync import sync_benchmark_entries

                await sync_benchmark_entries(
                    pool=pool,
                    evals_resource_id=resource_id,
                    model_ids=item.model_ids or [],
                    model_flag_ids=item.model_flag_ids or [],
                    model_rubric_ids=item.model_rubric_ids or [],
                    model_position_ids=item.model_position_ids or [],
                    department_ids=item.department_ids or [],
                    flag_ids=item.flag_ids or [],
                )
            except Exception as sync_err:
                logger.warning(f"sync_benchmark_entries failed (non-fatal): {sync_err}")

    # All-matching path threads soft-skipped rows back into the
    # response so the client can surface "X updated, Y skipped" in
    # one toast. Explicit path's ``skipped_results`` is empty.
    return UpdateEvalApiResponse(
        results=results + skipped_results,
        idempotency_key=idempotency_key,
    )
