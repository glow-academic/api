"""Parameter create logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_create — permission check
  3. resolve_parameter_values — raw value → ID resolution
  4. create_parameter_artifact — junction writes
  5. create_denormalized_snapshot — parameters_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.parameter.permissions_context import (
    create_denormalized_snapshot,
    resolve_parameter_values,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.parameter.refresh import refresh_parameter_impl
from app.tools.artifacts.parameter.create import (
    create_parameter as create_parameter_artifact,
)
from app.tools.artifacts.parameter.get import get_parameters as get_parameter_artifacts
from app.tools.resources.parameters.get import get_parameters as get_parameter_resources
from app.infra.parameter.types import (
    CreateParameterApiRequest,
    ParameterResultItem,
    CreateParameterApiResponse,
)


async def create_parameter_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: CreateParameterApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> CreateParameterApiResponse:
    """Parameter bulk create using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. compute_can_create — single check (applies to all items)
      3. Per-item value resolution (raw → ID, required field enforcement)
      4. Single transaction: create_parameter_artifact + denormalized snapshot per item
      5. canonical parameter refresh
    """
    from app.infra.parameter.permissions import compute_can_create

    # ── Merge ack fields from request (HTTP) or params (generation pipeline)
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

    # ── Step 2: Permission check ───────────────────────────────────────

    requested_department_ids = [
        department_id for item in items for department_id in (item.department_ids or [])
    ]
    if not compute_can_create(
            role_level=profile.role_level, role_permissions=profile.role_permissions,
            department_ids=requested_department_ids or None,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create parameters.",
        )

    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await create_parameter_artifact(
                        conn,
                        id=idempotency_key,
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
                    id=artifact.id,
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
            return CreateParameterApiResponse(
                results=[
                    ParameterResultItem(
                        success=True,
                        parameter_id=idempotency_key,
                        message="Parameter accepted",
                    )
                ],
                idempotency_key=idempotency_key,
            )

        return CreateParameterApiResponse(
            results=[
                ParameterResultItem(
                    success=True,
                    message="Parameter rejected",
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
                conn, redis, item, is_create=True
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
        return CreateParameterApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    # ── Step 4: Denormalized snapshots (skip when soft) ───────────────

    results: list[ParameterResultItem] = []
    snapshot_ids: list[UUID] = []

    if not soft:
        for item in items:
            parameters_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                id=item.resource_id,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                field_ids=item.field_ids,
                persona_parameter=item.persona_parameter or False,
                document_parameter=item.document_parameter or False,
                scenario_parameter=item.scenario_parameter or False,
                video_parameter=item.video_parameter or False,
            )
            snapshot_ids.append(parameters_resource_id)

    # ── Step 5: Artifact writes ───────────────────────────────────────

    for idx, item in enumerate(items):
        async with pool.acquire() as conn:
            async with conn.transaction():
                result = await create_parameter_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=item.department_ids,
                    flag_ids=item.flag_ids,
                    field_ids=item.field_ids,
                    parameter_ids=[snapshot_ids[idx]] if snapshot_ids else None,
                    soft=soft,
                )

        results.append(
            ParameterResultItem(
                success=True,
                parameter_id=result.id,
                message=(
                    "Parameter created (pending acceptance)"
                    if soft
                    else "Parameter created successfully"
                ),
            )
        )

    # ── Step 6: Canonical refresh ─────────────────────────────────────

    await refresh_parameter_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=idempotency_key or (results[0].parameter_id if results else None),
    )

    return CreateParameterApiResponse(results=results, idempotency_key=idempotency_key)
