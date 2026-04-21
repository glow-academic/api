"""Department update logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.department.permissions_context import (
    create_denormalized_snapshot,
    resolve_department_permissions_context,
    resolve_department_values,
)
from app.infra.department.refresh import refresh_department_impl
from app.infra.department.types import UpdateDepartmentApiRequest, UpdateDepartmentApiResponse
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.department.get import (
    get_departments as get_department_artifacts,
)
from app.tools.artifacts.department.update import (
    _UNSET,
)
from app.tools.artifacts.department.update import (
    update_department as update_department_artifact,
)


async def update_department_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdateDepartmentApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdateDepartmentApiResponse:
    """Department bulk update using composable infra functions."""
    from app.infra.department.permissions import compute_can_edit
    from app.infra.department.types import DepartmentResultItem
    from app.infra.identity.keycloak_sync import perform_keycloak_sync

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    items = request.departments

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
            perms = await resolve_department_permissions_context(conn, item.department_id)
            if not perms.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Department {item.department_id} not found.",
                )
            if not compute_can_edit(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
                usage_count=perms.usage_count,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this department.",
                )

    if accept is not None and idempotency_key is not None:
        if not accept:
            return UpdateDepartmentApiResponse(
                results=[
                    DepartmentResultItem(
                        success=True,
                        department_id=item.department_id,
                        message="Update rejected",
                    )
                    for item in items
                ],
                idempotency_key=idempotency_key,
            )
        soft = False

    has_errors = False
    error_results: list[DepartmentResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_department_values(conn, redis, item, is_create=False)
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
        return UpdateDepartmentApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    results: list[DepartmentResultItem] = []
    saved_department_ids: list[UUID] = []

    for item in items:
        async with pool.acquire() as conn:
            existing = await get_department_artifacts(
                conn,
                [item.department_id],
                names=True,
                descriptions=True,
                settings=True,
            )

        departments_resource_id = None
        if not soft:
            if existing:
                art = existing[0]
                eff_name_id = item.name_id or (art.name_ids[0] if art.name_ids else None)
                eff_desc_id = item.description_id or (art.description_ids[0] if art.description_ids else None)
                eff_setting_ids = item.settings_ids if item.settings_ids is not None else list(art.settings_ids or [])
            else:
                eff_name_id = item.name_id
                eff_desc_id = item.description_id
                eff_setting_ids = item.settings_ids

            departments_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                name_id=eff_name_id,
                description_id=eff_desc_id,
                setting_ids=eff_setting_ids,
            )

        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_department_artifact(
                    conn,
                    item.department_id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id if item.description_id else _UNSET,
                    department_ids=[departments_resource_id] if departments_resource_id else None,
                    flag_ids=[item.active_flag_id] if item.active_flag_id else None,
                    settings_ids=item.settings_ids,
                    soft=soft,
                )

        saved_department_ids.append(item.department_id)
        results.append(
            DepartmentResultItem(
                success=True,
                department_id=item.department_id,
                message=(
                    "Department update accepted"
                    if accept is not None and idempotency_key is not None
                    else "Department updated (pending acceptance)"
                    if soft
                    else "Department updated successfully"
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

    return UpdateDepartmentApiResponse(
        results=results,
        idempotency_key=idempotency_key,
    )
