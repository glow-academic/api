"""Parameter duplicate logic — composable infra architecture.

Core duplicate function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. compute_can_duplicate — permission check
  3. get_parameters — fetch original with all junction IDs
  4. create_name — new name resource ("{name} Copy")
  5. create_parameter — new artifact with original's IDs + new name
  6. invalidate_tags — cache invalidation

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
from app.tools.artifacts.parameter.create import (
    create_parameter as create_parameter_artifact,
)
from app.tools.artifacts.parameter.get import get_parameters
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.utils.cache.invalidate_tags import invalidate_tags


async def duplicate_parameter_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    parameter_id: UUID,
    session_id: UUID | None = None,
) -> DuplicateParameterApiResponse:
    """Parameter duplicate using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role
      2. compute_can_duplicate -> permission check
      3. get_parameters -> fetch original with all junctions
      4. create_name("{name} Copy") -> new name resource
      5. create_parameter -> new artifact with original IDs (no flag)
      6. invalidate_tags
    """

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

    if not compute_can_duplicate(user_role=profile.role):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to duplicate this parameter.",
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
            name_resources = await get_names(conn, original.name_ids, redis)
            if name_resources:
                original_name = name_resources[0].name or "Unknown"

        new_name_resource = await create_name(conn, f"{original_name} Copy", redis)

    # -- Step 5: Create new parameter artifact (no flag — no parameter_active) --

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_parameter_artifact(
                conn,
                name_id=new_name_resource.id,
                description_id=original.description_ids[0]
                if original.description_ids
                else None,
                department_ids=original.department_ids,
                field_ids=original.field_ids,
                parameter_ids=original.parameter_ids,
                flag_ids=None,
            )

    # -- Step 6: Invalidate cache -----------------------------------------------

    await invalidate_tags(["parameters"], redis=redis)

    return DuplicateParameterApiResponse(
        success=True,
        parameter_id=result.id,
        message=f"Parameter '{original_name}' duplicated successfully",
    )
