"""Eval create logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.eval.permissions_context import (
    create_denormalized_snapshot,
    resolve_eval_values,
)
from app.infra.eval.refresh import refresh_eval_impl
from app.infra.eval.types import (
    CreateEvalApiRequest,
    CreateEvalApiResponse,
    EvalResultItem,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.eval.create import create_eval as create_eval_artifact
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def create_eval_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: CreateEvalApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> CreateEvalApiResponse:
    """Eval bulk create using composable infra functions."""
    from app.infra.eval.permissions import compute_can_create

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    items = request.evals
    if idempotency_key is not None and len(items) == 1 and items[0].id is None:
        items = [items[0].model_copy(update={"id": idempotency_key})]

    profile = await resolve_profile_identity_context(
        pool,
        profile_id,
        redis,
        session_id=session_id,
        draft_id=draft_id,
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
            detail="You don't have permission to create evals.",
        )

    if accept is not None and idempotency_key is not None:
        if not accept:
            return CreateEvalApiResponse(
                results=[
                    EvalResultItem(
                        success=True,
                        eval_id=idempotency_key,
                        message="Eval rejected",
                    )
                ],
                idempotency_key=idempotency_key,
            )
        soft = False

    has_errors = False
    error_results: list[EvalResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_eval_values(conn, redis, item, is_create=True)
            if item_errors:
                has_errors = True
                error_results.append(
                    EvalResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(EvalResultItem(success=True, message="Validated"))

    if has_errors:
        return CreateEvalApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    results: list[EvalResultItem] = []
    sync_items: list[tuple[UUID, object]] = []
    snapshot_ids: list[UUID] = []

    if not soft:
        for item in items:
            evals_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                id=item.resource_id,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                model_ids=item.model_ids,
                model_rubric_ids=item.model_rubric_ids,
                model_flag_ids=item.model_flag_ids,
                model_position_ids=item.model_position_ids,
            )
            snapshot_ids.append(evals_resource_id)
            sync_items.append((evals_resource_id, item))

    async with pool.acquire() as conn:
        async with conn.transaction():
            for idx, item in enumerate(items):
                combined_flag_ids = list(item.flag_ids or [])
                if item.active_flag_id:
                    combined_flag_ids.append(item.active_flag_id)

                result = await create_eval_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=item.department_ids,
                    flag_ids=combined_flag_ids or None,
                    model_ids=item.model_ids,
                    model_flag_ids=item.model_flag_ids,
                    model_rubric_ids=item.model_rubric_ids,
                    model_position_ids=item.model_position_ids,
                    eval_ids=[snapshot_ids[idx]] if snapshot_ids else None,
                    soft=soft,
                )

                results.append(
                    EvalResultItem(
                        success=True,
                        eval_id=result.id,
                        message=(
                            "Eval accepted"
                            if accept is not None and idempotency_key is not None
                            else "Eval created (pending acceptance)"
                            if soft
                            else "Eval created successfully"
                        ),
                    )
                )

    if not soft:
        await refresh_eval_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (results[0].eval_id if results else None),
        )

        for resource_id, item in sync_items:
            try:
                from app.infra.benchmark.sync import sync_benchmark_entries

                await sync_benchmark_entries(
                    pool=pool,
                    evals_resource_id=resource_id,
                    model_ids=item.model_ids or [],
                    model_flag_ids=item.model_flag_ids or [],
                    model_rubric_ids=item.model_rubric_ids or [],
                    model_position_ids=item.model_position_ids or [],
                    department_ids=item.department_ids or [],
                )
            except Exception as sync_err:
                logger.warning(f"sync_benchmark_entries failed (non-fatal): {sync_err}")

    return CreateEvalApiResponse(
        results=results,
        idempotency_key=idempotency_key,
    )
