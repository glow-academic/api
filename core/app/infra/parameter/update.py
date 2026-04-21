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

from app.infra.parameter.permissions_context import (
    create_denormalized_snapshot,
    resolve_parameter_permissions_context,
    resolve_parameter_values,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.parameter.refresh import refresh_parameter_impl
from app.tools.artifacts.parameter.get import get_parameters as get_parameter_artifacts
from app.tools.resources.parameters.get import get_parameters as get_parameter_resources
from app.tools.artifacts.parameter.update import (
    _UNSET,
)
from app.tools.artifacts.parameter.update import (
    update_parameter as update_parameter_artifact,
)

from app.infra.parameter.types import (
    UpdateParameterApiRequest,
    UpdateParameterApiResponse,
)


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

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. Per-item: resolve_parameter_permissions_context → exists + compute_can_edit
      3. Per-item value resolution (raw → ID, no required field enforcement)
      4. Single transaction: update_parameter_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
    from app.infra.parameter.permissions import compute_can_edit
    from app.infra.parameter.types import (
        ParameterResultItem,
    )

    # Merge ack fields from request (HTTP) or params (generation pipeline)
    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key and accept is None:
        accept = request.accept

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

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            perms = await resolve_parameter_permissions_context(conn, item.parameter_id)
            if not perms.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Parameter {item.parameter_id} not found.",
                )
            if not compute_can_edit(
                role_level=profile.role_level, role_permissions=profile.role_permissions,
                parameter_department_ids=perms.department_ids,
                active_scenario_count=perms.active_scenario_count,
                user_department_ids=profile.department_ids,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this parameter.",
                )

    # ── ACK short-circuit / promotion ─────────────────────────────────

    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await update_parameter_artifact(
                        conn,
                        idempotency_key,
                        soft=False,
                    )

            async with pool.acquire() as conn:
                artifacts = await get_parameter_artifacts(
                    conn,
                    [idempotency_key],
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
                    parameter_id=idempotency_key,
                    message="Update accepted" if accept else "Update rejected",
                )
            ],
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
                    item.parameter_id,
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

        results.append(
            ParameterResultItem(
                success=True,
                parameter_id=item.parameter_id,
                message=(
                    "Parameter updated (pending acceptance)"
                    if soft
                    else "Parameter updated successfully"
                ),
            )
        )

    # ── Step 5: Canonical refresh ──────────────────────────────────────

    await refresh_parameter_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=idempotency_key or (results[0].parameter_id if results else None),
    )

    return UpdateParameterApiResponse(
        results=results,
        idempotency_key=idempotency_key,
    )
