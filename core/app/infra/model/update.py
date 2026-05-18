"""Model update logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.model.permissions_context import (
    create_denormalized_snapshot,
    resolve_model_permissions_context,
    resolve_model_values,
)
from app.infra.model.refresh import refresh_model_impl
from app.infra.model.types import (
    ListModelApiModel,
    ModelResultItem,
    UpdateModelApiRequest,
    UpdateModelApiResponse,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.model.update import _UNSET
from app.tools.artifacts.model.update import (
    update_model as update_model_artifact,
)
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls

ARTIFACT = "model"


async def update_model_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdateModelApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdateModelApiResponse:
    """Model bulk update using composable infra functions.

    Three call shapes:
      - First call (explicit): ``request.models`` required.
      - First call (all-matching): ``request.all=true`` plus ``patch``
        plus filter fields. The impl resolves matching ids, clones
        the patch per id (stamping each id), then runs the existing
        per-row update flow. Per-row permission failures soft-skip.
      - Ack call: ``idempotency_key`` + ``accept`` only.
    """
    from app.infra.model.permissions import compute_can_edit

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    # ── Short-circuit: ack path ───────────────────────────────────────
    # Ack-hoisted ABOVE perm checks because ``request.models`` is None
    # under the ack path; the dormant row is located solely by
    # ``idempotency_key``. The original impl ran perm checks first,
    # which broke under ack/all paths. Mirror persona/scenario shape.
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "update":
            raise HTTPException(
                status_code=404,
                detail="No pending model update for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await update_model_artifact(conn, target_id, soft=False)

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

        await refresh_model_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )
        return UpdateModelApiResponse(
            results=[
                ModelResultItem(
                    success=True,
                    model_id=target_id,
                    message="Update accepted" if accept else "Update rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── All-matching path: resolve ids + synthesize per-row items ─────
    # Past the ack short-circuit and ``all=true`` ⇒ enumerate every
    # model matching the filter, then clone ``request.patch`` per id
    # (stamping the resolved id). The downstream per-row flow runs
    # unchanged. Per-row permission failures soft-skip (collected into
    # ``skipped_results`` and threaded into the final response).
    skipped_results: list[ModelResultItem] = []

    if request.all:
        if request.patch is None:
            raise HTTPException(
                status_code=400,
                detail="`patch` is required when `all=true` "
                "(it carries the shared change set applied to every matched row).",
            )
        from app.infra.model.resolve_matching_ids import resolve_matching_model_ids
        from app.infra.model.types import UpdateModelItem

        matching = await resolve_matching_model_ids(
            pool, redis,
            profile_id=profile_id,
            search=request.search,
            filter_provider_ids=request.filter_provider_ids,
            filter_department_ids=request.filter_department_ids,
            filter_agent_ids=request.filter_agent_ids,
            provider_search=request.provider_search,
            department_search=request.department_search,
            agent_search=request.agent_search,
            flag_search=request.flag_search,
        )
        excluded = set(request.excluded_ids or [])
        resolved_ids = [mid for mid in matching if mid not in excluded]

        if not resolved_ids:
            return UpdateModelApiResponse(results=[], idempotency_key=idempotency_key)

        patch_fields = request.patch.model_dump(exclude_unset=True, exclude={"id"})
        synth_items = [UpdateModelItem(id=mid, **patch_fields) for mid in resolved_ids]
        request = request.model_copy(update={"models": synth_items})

    # ── First-call requirements ───────────────────────────────────────
    if not request.models:
        raise HTTPException(
            status_code=400,
            detail="`request.models` is required for first-call update "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with `patch` and filter fields).",
        )

    items = request.models

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

    # ── Per-item permission check ────────────────────────────────────
    # Explicit path fails fast (existing behavior).
    # All-matching path soft-skips so the response carries per-row
    # outcomes without aborting rows the user CAN edit.
    is_all_matching = bool(request.all)
    permitted_items: list = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            perms = await resolve_model_permissions_context(conn, item.id)
            if not perms.exists:
                if is_all_matching:
                    skipped_results.append(ModelResultItem(
                        success=False, model_id=item.id,
                        message=f"Model {item.id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Model {item.id} not found.",
                )
            if not compute_can_edit(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
                model_department_ids=perms.department_ids,
                active_agent_count=perms.active_agent_count,
                user_department_ids=profile.department_ids,
            ):
                if is_all_matching:
                    skipped_results.append(ModelResultItem(
                        success=False, model_id=item.id,
                        message=f"No permission to update model {item.id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this model.",
                )
            permitted_items.append(item)

    if is_all_matching:
        items = permitted_items
        if not items:
            return UpdateModelApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    has_errors = False
    error_results: list[ModelResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_model_values(conn, redis, item, is_create=False)
            if item_errors:
                has_errors = True
                error_results.append(
                    ModelResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(ModelResultItem(success=True, message="Validated"))

    if has_errors:
        return UpdateModelApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    results: list[ModelResultItem] = []

    for item in items:
        models_resource_id = None
        if not soft:
            models_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                provider_id=item.provider_id,
                temperature_level_ids=item.temperature_level_ids,
                reasoning_level_ids=item.reasoning_level_ids,
                quality_ids=item.quality_ids,
                voice_ids=item.voice_ids,
                modality_ids=item.modality_ids,
                value_id=item.value_id,
            )

        combined_flag_ids = list(item.flag_ids or [])

        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_model_artifact(
                    conn,
                    item.id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id if item.description_id else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=combined_flag_ids or None,
                    modality_ids=item.modality_ids,
                    model_ids=[models_resource_id] if models_resource_id else None,
                    pricing_ids=item.pricing_ids,
                    provider_id=item.provider_id,
                    quality_ids=item.quality_ids,
                    reasoning_level_ids=item.reasoning_level_ids,
                    temperature_level_ids=item.temperature_level_ids,
                    value_id=item.value_id,
                    voice_ids=item.voice_ids,
                    soft=soft,
                )

                # Pending ledger row tied to this tool call.
                if soft and idempotency_key is not None:
                    await create_soft_call(
                        conn,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="update",
                        artifact_id=item.id,
                    )

        results.append(
            ModelResultItem(
                success=True,
                model_id=item.id,
                message=(
                    "Model updated (pending acceptance)"
                    if soft
                    else "Model updated successfully"
                ),
            )
        )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    if not soft:
        await refresh_model_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (results[0].model_id if results else None),
        )

    # Hydrate full row content for the client. See
    # ``hydrate_model_list_rows``. Soft-pending updates skip hydration:
    # the dormant change isn't visible in the active row yet (artifact
    # is deactivated until ack-accept promotes it).
    models: list[ListModelApiModel] | None = None
    if not soft:
        from app.infra.model.hydrate_list_rows import hydrate_model_list_rows
        updated_ids = [r.model_id for r in results if r.success and r.model_id is not None]
        if updated_ids:
            models = await hydrate_model_list_rows(
                pool, redis, profile_id=profile_id, model_ids=updated_ids,
            )

    # All-matching path threads soft-skipped rows back into the
    # response so the client can surface "X updated, Y skipped" in
    # one toast. Explicit path's ``skipped_results`` is empty.
    return UpdateModelApiResponse(
        results=results + skipped_results,
        idempotency_key=idempotency_key,
        models=models,
    )
