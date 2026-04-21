"""Rubric update logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.rubric.permissions_context import (
    create_denormalized_snapshot,
    resolve_rubric_permissions_context,
    resolve_rubric_values,
)
from app.infra.rubric.refresh import refresh_rubric_impl
from app.infra.rubric.types import (
    UpdateRubricApiRequest,
    UpdateRubricApiResponse,
)
from app.tools.artifacts.rubric.update import (
    _UNSET,
)
from app.tools.artifacts.rubric.update import (
    update_rubric as update_rubric_artifact,
)


async def update_rubric_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdateRubricApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdateRubricApiResponse:
    """Rubric bulk update using composable infra functions."""
    from app.infra.rubric.permissions import compute_can_edit
    from app.infra.rubric.types import RubricResultItem

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    items = request.rubrics

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

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            perms = await resolve_rubric_permissions_context(conn, item.rubric_id)
            if not perms.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Rubric {item.rubric_id} not found.",
                )
            if not compute_can_edit(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
                rubric_department_ids=perms.department_ids,
                active_simulation_count=perms.active_simulation_count,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this rubric.",
                )

    if accept is not None and idempotency_key is not None:
        if not accept:
            return UpdateRubricApiResponse(
                results=[
                    RubricResultItem(
                        success=True,
                        rubric_id=item.rubric_id,
                        message="Update rejected",
                    )
                    for item in items
                ],
                idempotency_key=idempotency_key,
            )
        soft = False

    has_errors = False
    error_results: list[RubricResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_rubric_values(conn, redis, item, is_create=False)
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
        return UpdateRubricApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    results: list[RubricResultItem] = []

    for item in items:
        rubrics_resource_id = None
        if not soft:
            rubrics_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                standard_group_ids=item.standard_group_ids,
                simulation_rubric=bool(item.simulation_rubric_flag_id),
                video_rubric=bool(item.video_rubric_flag_id),
            )

        combined_flag_ids = [
            fid
            for fid in [
                item.active_flag_id,
                item.simulation_rubric_flag_id,
                item.video_rubric_flag_id,
            ]
            if fid
        ]

        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_rubric_artifact(
                    conn,
                    item.rubric_id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id if item.description_id else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=combined_flag_ids or None,
                    point_ids=item.point_ids,
                    standard_group_ids=item.standard_group_ids,
                    standard_ids=item.standard_ids,
                    rubric_ids=[rubrics_resource_id] if rubrics_resource_id else None,
                    soft=soft,
                )

        results.append(
            RubricResultItem(
                success=True,
                rubric_id=item.rubric_id,
                message=(
                    "Rubric update accepted"
                    if accept is not None and idempotency_key is not None
                    else "Rubric updated (pending acceptance)"
                    if soft
                    else "Rubric updated successfully"
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

    return UpdateRubricApiResponse(
        results=results,
        idempotency_key=idempotency_key,
    )
