"""Parameter delete logic — composable infra architecture.

Core delete function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. resolve_parameter_permissions_context — per-item exists, departments, usage
  3. compute_can_delete — permission check
  4. delete_parameters — bulk delete tool
  5. refresh_parameter_impl — canonical refresh
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.parameter.permissions import compute_can_delete
from app.infra.parameter.permissions_context import (
    resolve_parameter_permissions_context,
)
from app.infra.delete.delete_artifact import restore_artifacts
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.parameter.refresh import refresh_parameter_impl
from app.infra.parameter.types import (
    DeleteParameterApiResponse,
    DeleteParameterResult,
)
from app.tools.artifacts.parameter.delete import delete_parameters
from app.tools.artifacts.parameter.get import get_parameters
from app.tools.resources.names.get import get_names


async def delete_parameter_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    ids: list[UUID],
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> DeleteParameterApiResponse:
    """Parameter bulk delete using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role
      2. Per-item: resolve_parameter_permissions_context -> exists, departments, usage
      3. Per-item: compute_can_delete -> permission check (fail fast)
      4. Fetch names for result messages
      5. Single transaction: delete_parameters -> bulk delete
      6. invalidate_tags
    """

    # -- Step 1: Profile context -----------------------------------------------

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

    # -- Step 2+3: Per-item permission checks (fail fast) ----------------------

    async with pool.acquire() as conn:
        for idx, parameter_id in enumerate(ids):
            ctx = await resolve_parameter_permissions_context(conn, parameter_id)

            if not ctx.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Parameter {parameter_id} not found.",
                )

            if not compute_can_delete(
                role_level=profile.role_level, role_permissions=profile.role_permissions,
                parameter_department_ids=ctx.department_ids,
                active_scenario_count=ctx.active_scenario_count,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this parameter.",
                )

    # -- Short-circuit: ack path ----------------------------------------------
    if accept is not None and idempotency_key is not None:
        if accept:
            # Confirm deletion: no-op (already deactivated by soft delete)
            pass
        else:
            # Reject: restore soft-deleted artifacts
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await restore_artifacts(
                        conn,
                        table="parameter_artifact",
                        ids=ids,
                    )

        await refresh_parameter_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key or (ids[0] if ids else None),
        )

        return DeleteParameterApiResponse(
            results=[
                DeleteParameterResult(
                    success=True,
                    parameter_id=parameter_id,
                    message=(
                        "Delete confirmed"
                        if accept
                        else "Delete rejected — parameter restored"
                    ),
                )
                for parameter_id in ids
            ],
            idempotency_key=idempotency_key,
        )

    # -- Step 4: Fetch names for result messages -------------------------------

    async with pool.acquire() as conn:
        name_map: dict[UUID, str] = {}
        artifacts = await get_parameters(conn, ids, names=True)
        for artifact in artifacts:
            name = "Unknown"
            if artifact.name_ids:
                name_resources = await get_names(conn, artifact.name_ids, redis)
                if name_resources:
                    name = name_resources[0].name or "Unknown"
            name_map[artifact.id] = name

    # -- Step 5: Single transaction -- bulk delete -----------------------------

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await delete_parameters(conn, ids, soft=soft)

    # -- Step 6: Canonical refresh --------------------------------------------

    await refresh_parameter_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=idempotency_key or (result.deleted_ids[0] if result.deleted_ids else None),
    )

    results = [
        DeleteParameterResult(
            success=True,
            parameter_id=pid,
            message=(
                f"Parameter '{name_map.get(pid, 'Unknown')}' deleted (pending confirmation)"
                if soft
                else f"Parameter '{name_map.get(pid, 'Unknown')}' deleted successfully"
            ),
        )
        for pid in result.deleted_ids
    ]

    return DeleteParameterApiResponse(results=results, idempotency_key=idempotency_key)
