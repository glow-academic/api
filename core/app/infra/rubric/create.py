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

    # Denormalize point values from IDs for snapshot / downstream use.
    # pass_points = value of the referenced pass-type Points resource.
    # total_points = sum of selected standards' points (computed, not written).
    from app.tools.resources.flags.search import search_flags
    from app.tools.resources.points.get import get_points
    from app.tools.resources.standards.get import get_standards

    async def _denorm_points(item) -> tuple[int | None, int | None]:
        pass_value: int | None = None
        total_value: int | None = None
        async with pool.acquire() as conn:
            if item.pass_points_id:
                rows = await get_points(conn, [item.pass_points_id], redis, bypass_cache=True)
                pass_value = rows[0].value if rows else None
            if item.standard_ids:
                rows = await get_standards(conn, list(item.standard_ids), redis, bypass_cache=True)
                total_value = sum((r.points or 0) for r in rows) if rows else 0
        return pass_value, total_value

    # Build a flag-id → row map so per-type bools (simulation_rubric,
    # video_rubric) for the snapshot can be derived from the canonical
    # flag_ids list. Same approach as the draft resolver.
    async def _flag_bools_by_type(item) -> dict[str, bool]:
        if not item.flag_ids:
            return {}
        async with pool.acquire() as conn:
            flag_rows = await search_flags(
                conn, redis, search=None, limit_count=1000, bypass_cache=True,
            )
        rows_by_id = {row.id: row for row in flag_rows if getattr(row, "id", None)}
        out: dict[str, bool] = {}
        for fid in item.flag_ids:
            row = rows_by_id.get(fid)
            if not row:
                continue
            rtype = getattr(row, "type", None) or getattr(row, "name", None)
            rval = getattr(row, "value", None)
            if rtype and rval is not None:
                out[rtype] = bool(rval)
        return out

    if not soft:
        for item in items:
            pass_value, total_value = await _denorm_points(item)
            flag_bools = await _flag_bools_by_type(item)
            rubrics_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                id=item.resource_id,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                standard_group_ids=item.standard_group_ids,
                simulation_rubric=flag_bools.get("simulation_rubric", False),
                video_rubric=flag_bools.get("video_rubric", False),
                total_points=total_value,
                pass_points=pass_value,
            )
            snapshot_ids.append(rubrics_resource_id)

    async with pool.acquire() as conn:
        async with conn.transaction():
            for idx, item in enumerate(items):
                # Only pass points are writeable; total is derived on read.
                point_ids = [item.pass_points_id] if item.pass_points_id else None
                result = await create_rubric_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=item.department_ids,
                    flag_ids=item.flag_ids or None,
                    point_ids=point_ids,
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
