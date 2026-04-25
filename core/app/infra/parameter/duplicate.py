"""Parameter duplicate logic — composable infra architecture.

Core duplicate function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. compute_can_duplicate — permission check
  3. get_parameters — fetch original with all junction IDs
  4. create_name — new name resource ("{name} Copy")
  5. create_parameter — new artifact with original's IDs + new name
  6. refresh_parameter_impl — canonical refresh

Note: No flag search for parameter — there is no parameter_active flag type.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.parameter.permissions import compute_can_duplicate
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.parameter.types import (
    DuplicateParameterApiResponse,
)
from app.infra.parameter.refresh import refresh_parameter_impl
from app.tools.artifacts.parameter.create import (
    create_parameter as create_parameter_artifact,
)
from app.tools.artifacts.parameter.get import get_parameters
from app.tools.resources.parameters.get import get_parameters as get_parameter_resources
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names


async def duplicate_parameter_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    id: UUID,
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> DuplicateParameterApiResponse:
    """Parameter duplicate using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role
      2. compute_can_duplicate -> permission check
      3. get_parameters -> fetch original with all junctions
      4. create_name("{name} Copy") -> new name resource
      5. create_parameter -> new artifact with original IDs (no flag)
      6. refresh_parameter_impl -> canonical refresh
    """
    parameter_id = id  # alias: tools send 'id', internal code uses 'parameter_id'

    # -- Step 1: Profile context ------------------------------------------------

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

    # -- Step 2: Permission check -----------------------------------------------

    if not compute_can_duplicate(role_level=profile.role_level, role_permissions=profile.role_permissions):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to duplicate this parameter.",
        )

    # -- Short-circuit: ack path ----------------------------------------------

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
                artifacts = await get_parameters(
                    conn,
                    [idempotency_key],
                    names=True,
                    descriptions=True,
                    departments=True,
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
                from app.infra.parameter.permissions_context import create_denormalized_snapshot

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
        return DuplicateParameterApiResponse(
            success=True,
            parameter_id=idempotency_key,
            message="Duplicate accepted" if accept else "Duplicate rejected",
            idempotency_key=idempotency_key,
        )

    # -- Step 3: Fetch original parameter with all junctions --------------------

    async with pool.acquire() as conn:
        originals = await get_parameters(
            conn,
            [parameter_id],
            names=True,
            descriptions=True,
            departments=True,
            fields=True,
            parameters=True,
        )

    if not originals:
        raise HTTPException(
            status_code=404,
            detail=f"Parameter {parameter_id} not found.",
        )

    original = originals[0]

    # -- Step 4: Create new name resource ---------------------------------------

    async with pool.acquire() as conn:
        original_name = "Unknown"
        if original.name_ids:
            name_resources = await get_names(pool, original.name_ids, redis)
            if name_resources:
                original_name = name_resources[0].name or "Unknown"

        new_name_resource = await create_name(conn, f"{original_name} Copy", redis)

    # -- Step 5: Create new parameter artifact (no flag — no parameter_active) --

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_parameter_artifact(
                conn,
                id=idempotency_key,
                name_id=new_name_resource.id,
                description_id=original.description_ids[0]
                if original.description_ids
                else None,
                department_ids=original.department_ids,
                field_ids=original.field_ids,
                parameter_ids=original.parameter_ids,
                flag_ids=None,
                soft=soft,
            )

    # -- Step 6: Refresh --------------------------------------------------------

    if not soft:
        await refresh_parameter_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or result.id,
        )

    return DuplicateParameterApiResponse(
        success=True,
        parameter_id=result.id,
        message="Parameter duplicated (pending acceptance)"
        if soft
        else f"Parameter '{original_name}' duplicated successfully",
        idempotency_key=idempotency_key,
    )
