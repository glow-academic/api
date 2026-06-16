"""Field create logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_create — permission check
  3. resolve_field_values — raw value → ID resolution
  4. create_field_artifact — junction writes
  5. create_denormalized_snapshot — fields_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.field.permissions_context import (
    create_denormalized_snapshot,
    resolve_field_values,
)
from app.infra.field.refresh import refresh_field_impl
from app.infra.field.types import (
    CreateFieldApiRequest,
    CreateFieldApiResponse,
    FieldResultItem,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.artifacts.field.create import (
    create_field as create_field_artifact,
)
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.utils.cache.hedged_row import transaction_with_writeback

ARTIFACT = "field"


async def create_field_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: CreateFieldApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> CreateFieldApiResponse:
    """Field bulk create using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. compute_can_create — single check (applies to all items)
      3. Per-item value resolution (raw → ID, required field enforcement)
      4. Single transaction: create_field_artifact + denormalized snapshot per item
      5. canonical field refresh
    """
    from app.infra.field.permissions import compute_can_create

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    items = request.fields

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

    requested_department_ids = [
        department_id for item in items for department_id in (item.department_ids or [])
    ]
    with timed("permissions"):
        if not compute_can_create(
            role_level=profile.role_level, role_permissions=profile.role_permissions,
            department_ids=requested_department_ids or None,
        ):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to create fields.",
            )

    # ── ACK short-circuit ─────────────────────────────────────────────
    if accept is not None and idempotency_key is not None:
        with timed("ack"):
            async with pool.acquire() as conn:
                entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
            if entry is None or entry.status != "pending" or entry.operation != "create":
                raise HTTPException(
                    status_code=404,
                    detail="No pending field create for this call.",
                )
            target_id = entry.artifact_id

            if accept:
                async with pool.acquire() as conn:
                    async with transaction_with_writeback(conn):
                        await create_field_artifact(conn, id=target_id, soft=False)

            async with pool.acquire() as conn:
                await create_soft_call(
                    conn,
                    redis,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation="create",
                    artifact_id=target_id,
                    status="accepted" if accept else "rejected",
                )
            async with pool.acquire() as conn:
                await refresh_soft_calls(conn)

        with timed("refresh"):
            await refresh_field_impl(
                pool, redis,
                profile_id=profile_id, session_id=session_id,
                operation_key=idempotency_key,
            )

        return CreateFieldApiResponse(
            results=[
                FieldResultItem(
                    success=True,
                    field_id=target_id,
                    message="Field accepted" if accept else "Field rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[FieldResultItem] = []

    with timed("resolve_values"):
     async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_field_values(conn, redis, item, is_create=True)
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
        return CreateFieldApiResponse(results=error_results, idempotency_key=idempotency_key)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[FieldResultItem] = []

    if not soft:
        with timed("db_write"):
         for item in items:
            fields_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                id=item.resource_id,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                conditional_parameter_ids=item.conditional_parameter_ids,
            )

            async with pool.acquire() as conn:
                async with transaction_with_writeback(conn):
                    result = await create_field_artifact(
                        conn,
                        id=item.id,
                        name_id=item.name_id,
                        description_id=item.description_id,
                        department_ids=item.department_ids,
                        flag_ids=list(item.flag_ids) if item.flag_ids else None,
                        conditional_parameter_ids=item.conditional_parameter_ids,
                        field_ids=[fields_resource_id],
                        soft=False,
                    )

            results.append(
                FieldResultItem(
                    success=True,
                    field_id=result.id,
                    message=(
                        "Field accepted"
                        if accept is not None and idempotency_key is not None
                        else "Field created successfully"
                    ),
                )
            )

        with timed("refresh"):
            await refresh_field_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                soft=soft,
                operation_key=idempotency_key or (results[0].field_id if results else None),
            )
    else:
        for item in items:
            async with pool.acquire() as conn:
                async with transaction_with_writeback(conn):
                    result = await create_field_artifact(
                        conn,
                        id=item.id,
                        name_id=item.name_id,
                        description_id=item.description_id,
                        department_ids=item.department_ids,
                        flag_ids=list(item.flag_ids) if item.flag_ids else None,
                        conditional_parameter_ids=item.conditional_parameter_ids,
                        field_ids=None,
                        soft=True,
                    )

                    # Pending ledger row tied to this tool call.
                    if idempotency_key is not None:
                        await create_soft_call(
                            conn,
                            redis,
                            call_id=idempotency_key,
                            artifact=ARTIFACT,
                            operation="create",
                            artifact_id=result.id,
                        )

            results.append(
                FieldResultItem(
                    success=True,
                    field_id=result.id,
                    message="Field created (pending acceptance)",
                )
            )

        if idempotency_key is not None:
            async with pool.acquire() as conn:
                await refresh_soft_calls(conn)

    return CreateFieldApiResponse(results=results, idempotency_key=idempotency_key)
