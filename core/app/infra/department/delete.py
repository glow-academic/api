"""Department delete logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.delete.delete_artifact import restore_artifacts
from app.infra.department.permissions import compute_can_delete
from app.infra.department.permissions_context import (
    resolve_department_permissions_context,
)
from app.infra.department.refresh import refresh_department_impl
from app.infra.department.types import (
    DeleteDepartmentApiResponse,
    DeleteDepartmentResult,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.department.delete import delete_departments
from app.tools.artifacts.department.get import get_departments
from app.tools.resources.names.get import get_names


async def delete_department_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    ids: list[UUID],
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> DeleteDepartmentApiResponse:
    """Department bulk delete using composable infra functions."""
    from app.infra.identity.keycloak_sync import perform_keycloak_sync

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
        for idx, department_id in enumerate(ids):
            ctx = await resolve_department_permissions_context(conn, department_id)
            if not ctx.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Department {department_id} not found.",
                )
            if not compute_can_delete(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
                total_usage=ctx.usage_count,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this department.",
                )

    if accept is not None and idempotency_key is not None:
        if not accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await restore_artifacts(
                        conn,
                        table="department_artifact",
                        ids=ids,
                    )
        await refresh_department_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )
        try:
            for department_id in ids:
                await perform_keycloak_sync(department_id=str(department_id))
        except Exception:
            pass
        return DeleteDepartmentApiResponse(
            results=[
                DeleteDepartmentResult(
                    success=True,
                    department_id=department_id,
                    message="Delete confirmed" if accept else "Delete rejected — department restored",
                )
                for department_id in ids
            ],
            idempotency_key=idempotency_key,
        )

    name_map: dict[UUID, str] = {}
    async with pool.acquire() as conn:
        artifacts = await get_departments(conn, ids, names=True)
        for artifact in artifacts:
            name = "Unknown"
            if artifact.name_ids:
                name_resources = await get_names(conn, artifact.name_ids, redis)
                if name_resources:
                    name = name_resources[0].name or "Unknown"
            name_map[artifact.id] = name

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await delete_departments(conn, ids, soft=soft)

    await refresh_department_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=idempotency_key or (result.deleted_ids[0] if result.deleted_ids else None),
    )

    if not soft:
        try:
            for department_id in result.deleted_ids:
                await perform_keycloak_sync(department_id=str(department_id))
        except Exception:
            pass

    return DeleteDepartmentApiResponse(
        results=[
            DeleteDepartmentResult(
                success=True,
                department_id=pid,
                message=(
                    f"Department '{name_map.get(pid, 'Unknown')}' deleted (pending confirmation)"
                    if soft
                    else f"Department '{name_map.get(pid, 'Unknown')}' deleted successfully"
                ),
            )
            for pid in result.deleted_ids
        ],
        idempotency_key=idempotency_key,
    )
