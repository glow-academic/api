"""Rubric create logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.rubric.permissions_context import (
    create_denormalized_snapshot,
    resolve_rubric_values,
)
from app.infra.rubric.refresh import refresh_rubric_impl
from app.infra.rubric.types import (
    CreateRubricApiRequest,
    CreateRubricApiResponse,
    RubricResultItem,
)
from app.tools.artifacts.rubric.create import (
    create_rubric as create_rubric_artifact,
)


async def create_rubric_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: CreateRubricApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> CreateRubricApiResponse:
    """Rubric bulk create using composable infra functions."""
    from app.infra.rubric.permissions import compute_can_create

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    items = request.rubrics
    if idempotency_key is not None and len(items) == 1 and items[0].id is None:
        items = [items[0].model_copy(update={"id": idempotency_key})]

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

    if not compute_can_create(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
        department_ids=None,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create rubrics.",
        )

    if accept is not None and idempotency_key is not None:
        if not accept:
            return CreateRubricApiResponse(
                results=[
                    RubricResultItem(
                        success=True,
                        rubric_id=idempotency_key,
                        message="Rubric rejected",
                    )
                ],
                idempotency_key=idempotency_key,
            )
        soft = False

    has_errors = False
    error_results: list[RubricResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_rubric_values(conn, redis, item, is_create=True)
            if item_errors:
                has_errors = True
                error_results.append(
                    RubricResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(RubricResultItem(success=True, message="Validated"))

    if has_errors:
        return CreateRubricApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    results: list[RubricResultItem] = []
    snapshot_ids: list[UUID] = []

    if not soft:
        for item in items:
            rubrics_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                id=item.resource_id,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                standard_group_ids=item.standard_group_ids,
                simulation_rubric=bool(item.simulation_rubric_flag_id),
                video_rubric=bool(item.video_rubric_flag_id),
                total_points=item.total_points,
                pass_points=item.pass_points,
            )
            snapshot_ids.append(rubrics_resource_id)

    async with pool.acquire() as conn:
        async with conn.transaction():
            for idx, item in enumerate(items):
                combined_flag_ids = [
                    fid
                    for fid in [
                        item.active_flag_id,
                        item.simulation_rubric_flag_id,
                        item.video_rubric_flag_id,
                    ]
                    if fid
                ]
                result = await create_rubric_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=item.department_ids,
                    flag_ids=combined_flag_ids or None,
                    point_ids=item.point_ids,
                    standard_group_ids=item.standard_group_ids,
                    standard_ids=item.standard_ids,
                    rubric_ids=[snapshot_ids[idx]] if snapshot_ids else None,
                    soft=soft,
                )

                results.append(
                    RubricResultItem(
                        success=True,
                        rubric_id=result.id,
                        message=(
                            "Rubric accepted"
                            if accept is not None and idempotency_key is not None
                            else "Rubric created (pending acceptance)"
                            if soft
                            else "Rubric created successfully"
                        ),
                    )
                )

    if not soft:
        await refresh_rubric_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (results[0].rubric_id if results else None),
        )

    return CreateRubricApiResponse(
        results=results,
        idempotency_key=idempotency_key,
    )
