"""Field duplicate logic — composable infra architecture.

Core duplicate function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. compute_can_duplicate — permission check
  3. get_fields — fetch original with all junction IDs
  4. create_name — new name resource ("{name} Copy")
  5. search_flags — find inactive flag (field_active, value=false)
  6. create_field — new artifact with original's IDs + new name + inactive flag
  7. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.field.permissions import compute_can_duplicate
from app.infra.field.refresh import refresh_field_impl
from app.infra.field.types import (
    DuplicateFieldApiResponse,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.field.create import (
    create_field as create_field_artifact,
)
from app.tools.artifacts.field.get import get_fields
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names

ARTIFACT = "field"


async def duplicate_field_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    id: UUID,
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **_kwargs,
) -> DuplicateFieldApiResponse:
    """Field duplicate using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role
      2. compute_can_duplicate -> permission check
      3. get_fields -> fetch original with all junctions
      4. create_name("{name} Copy") -> new name resource
      5. search_flags -> find inactive flag (field_active, value=false)
      6. create_field -> new artifact with original IDs + inactive flag
      7. refresh_field_impl
    """
    field_id = id  # alias: tools send 'id', internal code uses 'field_id'

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
            detail="You don't have permission to duplicate this field.",
        )

    # -- ACK short-circuit -----------------------------------------------------
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "duplicate":
            raise HTTPException(
                status_code=404,
                detail="No pending field duplicate for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await create_field_artifact(conn, id=target_id, soft=False)

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                redis,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation="duplicate",
                artifact_id=target_id,
                status="accepted" if accept else "rejected",
            )
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

        await refresh_field_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )
        return DuplicateFieldApiResponse(
            success=True,
            field_id=target_id,
            idempotency_key=idempotency_key,
            message="Field duplicate accepted" if accept else "Field duplicate rejected",
        )

    # -- Step 3: Fetch original field with all junctions ------------------------

    async with pool.acquire() as conn:
        originals = await get_fields(
            conn,
            [field_id],
            names=True,
            descriptions=True,
            departments=True,
            conditional_parameters=True,
            fields=True,
        )

    if not originals:
        raise HTTPException(
            status_code=404,
            detail=f"Field {field_id} not found.",
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

    # -- Step 5: Find inactive flag (field_active, value=false) -----------------

    async with pool.acquire() as conn:
        inactive_flag_id: UUID | None = None
        flag_results = await search_flags(
            conn,
            redis,
            flag_type="field_active",
            field=True,
            limit_count=10,
        )
        inactive_match = next((f for f in flag_results if not f.value), None)
        if inactive_match:
            inactive_flag_id = inactive_match.id

    # -- Step 6: Create new field artifact with inactive flag -------------------

    flag_ids = [inactive_flag_id] if inactive_flag_id else None

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_field_artifact(
                conn,
                name_id=new_name_resource.id,
                description_id=original.description_ids[0]
                if original.description_ids
                else None,
                department_ids=original.department_ids,
                conditional_parameter_ids=original.conditional_parameter_ids,
                field_ids=original.field_ids,
                flag_ids=flag_ids,
                soft=soft,
            )

            # Pending ledger row tied to this tool call.
            if soft and idempotency_key is not None:
                await create_soft_call(
                    conn,
                    redis,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation="duplicate",
                    artifact_id=result.id,
                )

    # -- Step 7: Refresh via canonical helper ----------------------------------

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    if not soft:
        await refresh_field_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or result.id,
        )

    return DuplicateFieldApiResponse(
        success=True,
        field_id=result.id,
        idempotency_key=idempotency_key,
        message=(
            "Field duplicated (pending acceptance)"
            if soft
            else f"Field '{original_name}' duplicated successfully"
        ),
    )
