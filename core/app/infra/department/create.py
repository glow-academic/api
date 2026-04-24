"""Department create logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.department.permissions_context import (
    create_denormalized_snapshot,
    resolve_department_values,
)
from app.infra.department.refresh import refresh_department_impl
from app.infra.department.types import (
    CreateDepartmentApiRequest,
    CreateDepartmentApiResponse,
    DepartmentResultItem,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.department.create import (
    create_department as create_department_artifact,
)


async def create_department_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: CreateDepartmentApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> CreateDepartmentApiResponse:
    """Department bulk create using composable infra functions."""
    from app.infra.department.permissions import compute_can_create
    from app.infra.identity.keycloak_sync import perform_keycloak_sync

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    items = request.departments
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
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create departments.",
        )

    if accept is not None and idempotency_key is not None:
        if not accept:
            return CreateDepartmentApiResponse(
                results=[
                    DepartmentResultItem(
                        success=True,
                        department_id=idempotency_key,
                        message="Department rejected",
                    )
                ],
                idempotency_key=idempotency_key,
            )
        soft = False

    has_errors = False
    error_results: list[DepartmentResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_department_values(conn, redis, item, is_create=True)
            if item_errors:
                has_errors = True
                error_results.append(
                    DepartmentResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(DepartmentResultItem(success=True, message="Validated"))

    if has_errors:
        return CreateDepartmentApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    results: list[DepartmentResultItem] = []
    saved_department_ids: list[UUID] = []
    snapshot_ids: list[UUID] = []

    if not soft:
        for item in items:
            departments_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                id=item.resource_id,
                name_id=item.name_id,
                description_id=item.description_id,
                setting_ids=item.settings_ids,
            )
            snapshot_ids.append(departments_resource_id)

    async with pool.acquire() as conn:
        async with conn.transaction():
            for idx, item in enumerate(items):
                result = await create_department_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=[snapshot_ids[idx]] if snapshot_ids else None,
                    flag_ids=list(item.flag_ids) if item.flag_ids else None,
                    settings_ids=item.settings_ids,
                    soft=soft,
                )
                saved_department_ids.append(result.id)
                results.append(
                    DepartmentResultItem(
                        success=True,
                        department_id=result.id,
                        message=(
                            "Department accepted"
                            if accept is not None and idempotency_key is not None
                            else "Department created (pending acceptance)"
                            if soft
                            else "Department created successfully"
                        ),
                    )
                )

    if not soft:
        await refresh_department_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (results[0].department_id if results else None),
        )

        for department_id in saved_department_ids:
            try:
                await perform_keycloak_sync(department_id=str(department_id))
            except Exception:
                pass

    return CreateDepartmentApiResponse(
        results=results,
        idempotency_key=idempotency_key,
    )
