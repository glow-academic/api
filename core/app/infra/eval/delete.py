"""Eval delete logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.delete.delete_artifact import restore_artifacts
from app.infra.eval.permissions import compute_can_delete
from app.infra.eval.permissions_context import resolve_eval_permissions_context
from app.infra.eval.refresh import refresh_eval_impl
from app.infra.eval.types import DeleteEvalApiResponse, DeleteEvalResult
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.eval.delete import delete_evals
from app.tools.artifacts.eval.get import get_evals
from app.tools.resources.names.get import get_names


async def delete_eval_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    ids: list[UUID],
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> DeleteEvalApiResponse:
    """Eval bulk delete using composable infra functions."""
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
        for idx, eval_id in enumerate(ids):
            ctx = await resolve_eval_permissions_context(conn, eval_id)
            if not ctx.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Eval {eval_id} not found.",
                )
            if not compute_can_delete(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to delete this eval.",
                )

    if accept is not None and idempotency_key is not None:
        if not accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await restore_artifacts(
                        conn,
                        table="eval_artifact",
                        ids=ids,
                    )
        await refresh_eval_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )
        return DeleteEvalApiResponse(
            results=[
                DeleteEvalResult(
                    success=True,
                    eval_id=eval_id,
                    message="Delete confirmed" if accept else "Delete rejected — eval restored",
                )
                for eval_id in ids
            ],
            idempotency_key=idempotency_key,
        )

    name_map: dict[UUID, str] = {}
    async with pool.acquire() as conn:
        artifacts = await get_evals(conn, ids, names=True)
        for artifact in artifacts:
            name = "Unknown"
            if artifact.name_ids:
                name_resources = await get_names(conn, artifact.name_ids, redis)
                if name_resources:
                    name = name_resources[0].name or "Unknown"
            name_map[artifact.id] = name

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await delete_evals(conn, ids, soft=soft)

    await refresh_eval_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=idempotency_key or (result.deleted_ids[0] if result.deleted_ids else None),
    )

    return DeleteEvalApiResponse(
        results=[
            DeleteEvalResult(
                success=True,
                eval_id=pid,
                message=(
                    f"Eval '{name_map.get(pid, 'Unknown')}' deleted (pending confirmation)"
                    if soft
                    else f"Eval '{name_map.get(pid, 'Unknown')}' deleted successfully"
                ),
            )
            for pid in result.deleted_ids
        ],
        idempotency_key=idempotency_key,
    )
