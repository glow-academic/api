"""Model delete logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.delete.delete_artifact import restore_artifacts
from app.infra.model.permissions import compute_can_delete
from app.infra.model.permissions_context import resolve_model_permissions_context
from app.infra.model.refresh import refresh_model_impl
from app.infra.model.types import (
    DeleteModelApiResponse,
    DeleteModelResult,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.model.delete import delete_models
from app.tools.artifacts.model.get import get_models
from app.tools.resources.names.get import get_names


async def delete_model_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    model_ids: list[UUID],
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> DeleteModelApiResponse:
    """Model bulk delete using composable infra functions."""
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
        for idx, model_id in enumerate(model_ids):
            ctx = await resolve_model_permissions_context(conn, model_id)
            if not ctx.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Model {model_id} not found.",
                )
            if not compute_can_delete(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
                model_department_ids=ctx.department_ids,
                active_agent_count=ctx.active_agent_count,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this model.",
                )

    if accept is not None and idempotency_key is not None:
        if not accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await restore_artifacts(
                        conn,
                        table="model_artifact",
                        ids=model_ids,
                    )
        await refresh_model_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )
        return DeleteModelApiResponse(
            results=[
                DeleteModelResult(
                    success=True,
                    model_id=model_id,
                    message="Delete confirmed" if accept else "Delete rejected — model restored",
                )
                for model_id in model_ids
            ],
            idempotency_key=idempotency_key,
        )

    async with pool.acquire() as conn:
        name_map: dict[UUID, str] = {}
        artifacts = await get_models(conn, model_ids, names=True)
        for artifact in artifacts:
            name = "Unknown"
            if artifact.name_ids:
                name_resources = await get_names(conn, artifact.name_ids, redis)
                if name_resources:
                    name = name_resources[0].name or "Unknown"
            name_map[artifact.id] = name

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await delete_models(conn, model_ids, soft=soft)

    await refresh_model_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=idempotency_key or (result.deleted_ids[0] if result.deleted_ids else None),
    )

    return DeleteModelApiResponse(
        results=[
            DeleteModelResult(
                success=True,
                model_id=pid,
                message=(
                    f"Model '{name_map.get(pid, 'Unknown')}' deleted (pending confirmation)"
                    if soft
                    else f"Model '{name_map.get(pid, 'Unknown')}' deleted successfully"
                ),
            )
            for pid in result.deleted_ids
        ],
        idempotency_key=idempotency_key,
    )
