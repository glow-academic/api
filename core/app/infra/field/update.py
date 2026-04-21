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
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.field.refresh import refresh_field_impl
from app.tools.artifacts.field.update import (
    _UNSET,
)
from app.tools.artifacts.field.update import (
    update_field as update_field_artifact,
)

from app.infra.field.types import (
    UpdateFieldApiRequest,
    UpdateFieldApiResponse,
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

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. Per-item: resolve_field_permissions_context → exists + compute_can_edit
      3. Per-item value resolution (raw → ID, no required field enforcement)
      4. Single transaction: update_field_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
    from app.infra.field.permissions import compute_can_edit
    from app.infra.field.types import (
        FieldResultItem,
    )

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    items = request.fields

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

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            perms = await resolve_field_permissions_context(conn, item.field_id)
            if not perms.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Field {item.field_id} not found.",
                )
            if not compute_can_edit(
                role_level=profile.role_level, role_permissions=profile.role_permissions,
                field_department_ids=perms.department_ids,
                active_parameter_count=perms.active_parameter_count,
                user_department_ids=profile.department_ids,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this field.",
                )

    # ── ACK short-circuit ──────────────────────────────────────────────

    if accept is not None and idempotency_key is not None:
        if not accept:
            return UpdateFieldApiResponse(
                results=[
                    FieldResultItem(
                        success=True,
                        field_id=item.field_id,
                        message="Field update rejected",
                    )
                    for item in items
                ],
                idempotency_key=idempotency_key,
            )

        # ACK promote path reuses the normal update flow with soft=False.
        soft = False

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
                # Combine existing flag_id with active_flag_id
                combined_flag_ids = []
                if item.flag_id:
                    combined_flag_ids.append(item.flag_id)
                if item.active_flag_id:
                    combined_flag_ids.append(item.active_flag_id)

                await update_field_artifact(
                    conn,
                    item.field_id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id
                    if item.description_id
                    else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=combined_flag_ids or None,
                    conditional_parameter_ids=item.conditional_parameter_ids,
                    field_ids=[fields_resource_id] if fields_resource_id else None,
                    soft=soft,
                )

        results.append(
            FieldResultItem(
                success=True,
                field_id=item.field_id,
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

    return UpdateFieldApiResponse(
        results=results,
        idempotency_key=idempotency_key,
    )
