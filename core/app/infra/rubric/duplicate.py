"""Rubric duplicate logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.infra.rubric.permissions import compute_can_duplicate
from app.infra.rubric.refresh import refresh_rubric_impl
from app.infra.rubric.types import (
    DuplicateRubricApiResponse,
)
from app.tools.artifacts.rubric.create import (
    create_rubric as create_rubric_artifact,
)
from app.tools.artifacts.rubric.get import get_rubrics
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names

ARTIFACT = "rubric"


async def duplicate_rubric_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    id: UUID,
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> DuplicateRubricApiResponse:
    """Rubric duplicate using composable infra functions."""
    rubric_id = id  # alias: tools send 'id', internal code uses 'rubric_id'
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

    with timed("permissions"):
        if not compute_can_duplicate(
            role_level=profile.role_level,
            role_permissions=profile.role_permissions,
        ):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to duplicate this rubric.",
            )

    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "duplicate":
            raise HTTPException(
                status_code=404,
                detail="No pending rubric duplicate for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await create_rubric_artifact(
                        conn,
                        id=target_id,
                        soft=False,
                    )

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

        await refresh_rubric_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            operation_key=idempotency_key,
        )
        return DuplicateRubricApiResponse(
            success=True,
            rubric_id=target_id,
            message="Rubric duplicate accepted" if accept else "Rubric duplicate rejected",
            idempotency_key=idempotency_key,
        )

    with timed("hydrate"):
      async with pool.acquire() as conn:
        originals = await get_rubrics(
            conn,
            [rubric_id],
            names=True,
            descriptions=True,
            departments=True,
            points=True,
            standard_groups=True,
            standards=True,
            rubrics=True,
        )

    if not originals:
        raise HTTPException(
            status_code=404,
            detail=f"Rubric {rubric_id} not found.",
        )

    original = originals[0]

    # -- Department-subset guard --
    # Non-top-level users must belong to ALL of the original's
    # departments, else a Dept-A actor could clone a Dept-B rubric
    # they cannot even view (mirrors ``scenario.duplicate``).
    if not compute_can_duplicate(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
        rubric_department_ids=original.department_ids,
        user_department_ids=profile.department_ids,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to duplicate this rubric.",
        )

    async with pool.acquire() as conn:
        original_name = "Unknown"
        if original.name_ids:
            name_resources = await get_names(pool, original.name_ids, redis)
            if name_resources:
                original_name = name_resources[0].name or "Unknown"

        new_name_resource = await create_name(conn, f"{original_name} Copy", redis)

        inactive_flag_id: UUID | None = None
        flag_results = await search_flags(
            conn,
            redis,
            flag_type="rubric_active",
            rubric=True,
            limit_count=10,
        )
        inactive_match = next((flag for flag in flag_results if not flag.value), None)
        if inactive_match:
            inactive_flag_id = inactive_match.id

    flag_ids = [inactive_flag_id] if inactive_flag_id else None

    with timed("db_write"):
      async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_rubric_artifact(
                conn,
                id=idempotency_key,
                name_id=new_name_resource.id,
                description_id=original.description_ids[0] if original.description_ids else None,
                department_ids=original.department_ids,
                point_ids=original.point_ids,
                standard_group_ids=original.standard_group_ids,
                standard_ids=original.standard_ids,
                rubric_ids=original.rubric_ids,
                flag_ids=flag_ids,
                soft=soft,
            )

            if soft and idempotency_key is not None:
                await create_soft_call(
                    conn,
                    redis,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation="duplicate",
                    artifact_id=result.id,
                )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    if not soft:
        with timed("refresh"):
            await refresh_rubric_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                operation_key=idempotency_key or result.id,
            )

    # Hydrate the freshly-duplicated row so the client's ghost rail can
    # materialize it without a ``router.refresh()``. Single-element list
    # for shape consistency with create/update responses. Skipped on
    # soft writes.
    hydrated_rows = None
    if not soft:
        from app.infra.rubric.hydrate_list_rows import hydrate_rubric_list_rows

        hydrated_rows = await hydrate_rubric_list_rows(
            pool, redis, profile_id=profile_id, rubric_ids=[result.id],
        )

    return DuplicateRubricApiResponse(
        success=True,
        rubric_id=result.id,
        message=(
            "Rubric duplicate accepted"
            if accept is not None and idempotency_key is not None
            else "Rubric duplicated (pending acceptance)"
            if soft
            else f"Rubric '{original_name}' duplicated successfully"
        ),
        rubrics=hydrated_rows,
        idempotency_key=idempotency_key,
    )
