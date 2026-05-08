"""Field update logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. resolve_field_permissions_context — per-item access + edit check
  3. resolve_field_values — raw value → ID resolution
  4. update_field_artifact — junction writes (partial update)
  5. create_denormalized_snapshot — fields_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.field.permissions_context import (
    create_denormalized_snapshot,
    resolve_field_permissions_context,
    resolve_field_values,
)
from app.infra.field.refresh import refresh_field_impl
from app.infra.field.types import (
    UpdateFieldApiRequest,
    UpdateFieldApiResponse,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.field.update import (
    _UNSET,
)
from app.tools.artifacts.field.update import (
    update_field as update_field_artifact,
)


async def update_field_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdateFieldApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdateFieldApiResponse:
    """Field bulk update using composable infra functions.

    Three call shapes:
      - First call (explicit): ``request.fields`` required.
      - First call (all-matching): ``request.all=true`` plus ``patch``
        plus filter fields. The impl resolves matching ids, clones
        the patch per id (stamping each id), then runs the existing
        per-row update flow. Per-row permission failures soft-skip.
      - Ack call: ``idempotency_key`` + ``accept`` only.

    Flow (first call):
      1. (all-matching only) resolve_matching_field_ids → synth items
      2. resolve_profile_identity_context → role, department_ids
      3. Per-item: resolve_field_permissions_context → exists + compute_can_edit
      4. Per-item value resolution (raw → ID, no required field enforcement)
      5. Single transaction: update_field_artifact + denormalized snapshot per item
      6. canonical refresh
    """
    from app.infra.field.permissions import compute_can_edit
    from app.infra.field.types import (
        FieldResultItem,
    )

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    # ── All-matching path: resolve ids + synthesize per-row items ─────
    # Past the ack short-circuit consideration and ``all=true`` ⇒
    # enumerate every field matching the filter, then clone
    # ``request.patch`` per id (stamping the resolved id). The
    # downstream per-row flow runs unchanged. Per-row permission
    # failures soft-skip (collected into ``skipped_results`` and
    # threaded into the final response).
    skipped_results: list[FieldResultItem] = []

    if request.all and not (accept is not None and idempotency_key is not None):
        if request.patch is None:
            raise HTTPException(
                status_code=400,
                detail="`patch` is required when `all=true` "
                "(it carries the shared change set applied to every matched row).",
            )
        from app.infra.field.resolve_matching_ids import resolve_matching_field_ids
        from app.infra.field.types import UpdateFieldItem

        matching = await resolve_matching_field_ids(
            pool, redis,
            profile_id=profile_id,
            search=request.search,
            parameter_ids=request.parameter_ids,
            persona_ids=request.persona_ids,
            filter_department_ids=request.filter_department_ids,
            parameter_search=request.parameter_search,
            persona_search=request.persona_search,
            department_search=request.department_search,
            flag_search=request.flag_search,
        )
        excluded = set(request.excluded_ids or [])
        resolved_ids = [fid for fid in matching if fid not in excluded]

        if not resolved_ids:
            # Empty matching set — well-formed intent, just no rows.
            return UpdateFieldApiResponse(results=[], idempotency_key=idempotency_key)

        # Clone the patch per matched row, stamping the resolved id.
        # ``model_dump(exclude_unset=True, exclude={"id"})`` keeps sparse
        # semantics — only fields the client actually set are written.
        patch_fields = request.patch.model_dump(exclude_unset=True, exclude={"id"})
        synth_items = [UpdateFieldItem(id=fid, **patch_fields) for fid in resolved_ids]
        # Splice into the request shape downstream code expects.
        request = request.model_copy(update={"fields": synth_items})

    # ── First-call requirements ───────────────────────────────────────
    # Ack path exempt — locates dormant update by ``idempotency_key``.
    if not request.fields:
        if accept is not None and idempotency_key is not None:
            # Pure ack with no rows to act on — fall through to ack
            # short-circuit below.
            pass
        else:
            raise HTTPException(
                status_code=400,
                detail="`request.fields` is required for first-call update "
                "(or pass `idempotency_key` + `accept` for the ack call, "
                "or `all=true` with `patch` and filter fields).",
            )

    items = request.fields or []

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
            perms = await resolve_field_permissions_context(conn, item.id)
            if not perms.exists:
                if is_all_matching:
                    skipped_results.append(FieldResultItem(
                        success=False, field_id=item.id,
                        message=f"Field {item.id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Field {item.id} not found.",
                )
            if not compute_can_edit(
                role_level=profile.role_level, role_permissions=profile.role_permissions,
                field_department_ids=perms.department_ids,
                active_parameter_count=perms.active_parameter_count,
                user_department_ids=profile.department_ids,
            ):
                if is_all_matching:
                    skipped_results.append(FieldResultItem(
                        success=False, field_id=item.id,
                        message=f"No permission to update field {item.id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this field.",
                )

            permitted_items.append(item)

    if is_all_matching:
        items = permitted_items

    # ── ACK short-circuit ──────────────────────────────────────────────

    if accept is not None and idempotency_key is not None:
        if not accept:
            return UpdateFieldApiResponse(
                results=[
                    FieldResultItem(
                        success=True,
                        field_id=item.id,
                        message="Field update rejected",
                    )
                    for item in items
                ],
                idempotency_key=idempotency_key,
            )

        # ACK promote path reuses the normal update flow with soft=False.
        soft = False

    # All-matching path: every row was soft-skipped — return only
    # ``skipped_results`` without touching the DB.
    if is_all_matching and not items:
        return UpdateFieldApiResponse(
            results=skipped_results,
            idempotency_key=idempotency_key,
        )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[FieldResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_field_values(conn, redis, item, is_create=False)
            if item_errors:
                has_errors = True
                error_results.append(
                    FieldResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(FieldResultItem(success=True, message="Validated"))

    if has_errors:
        return UpdateFieldApiResponse(results=error_results, idempotency_key=idempotency_key)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[FieldResultItem] = []

    for item in items:
        fields_resource_id = None
        if not soft:
            fields_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                conditional_parameter_ids=item.conditional_parameter_ids,
            )

        # Artifact update inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_field_artifact(
                    conn,
                    item.id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id
                    if item.description_id
                    else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=list(item.flag_ids) if item.flag_ids else None,
                    conditional_parameter_ids=item.conditional_parameter_ids,
                    field_ids=[fields_resource_id] if fields_resource_id else None,
                    soft=soft,
                )

        results.append(
            FieldResultItem(
                success=True,
                field_id=item.id,
                message="Field updated (pending acceptance)" if soft else "Field updated successfully",
            )
        )

    if not soft:
        await refresh_field_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (results[0].field_id if results else None),
        )

    # All-matching path threads soft-skipped rows back into the
    # response so the client can surface "X updated, Y skipped" in
    # one toast. Explicit path's ``skipped_results`` is empty.
    return UpdateFieldApiResponse(
        results=results + skipped_results,
        idempotency_key=idempotency_key,
    )
