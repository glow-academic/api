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
from app.infra.server_timing import timed
from app.tools.artifacts.eval.create import create_eval as create_eval_artifact
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

ARTIFACT = "eval"


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
        if not compute_can_create(
            role_level=profile.role_level,
            role_permissions=profile.role_permissions,
        ):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to create evals.",
            )

    if accept is not None and idempotency_key is not None:
        with timed("ack"):
            async with pool.acquire() as conn:
                entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
            if entry is None or entry.status != "pending" or entry.operation != "create":
                raise HTTPException(
                    status_code=404,
                    detail="No pending eval create for this call.",
                )
            target_id = entry.artifact_id

            if accept:
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        await create_eval_artifact(conn, id=target_id, soft=False)

            async with pool.acquire() as conn:
                await create_soft_call(
                    conn,
                    redis,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation="create",
                    artifact_id=target_id,
                    status="accepted" if accept else "rejected",
                )
            async with pool.acquire() as conn:
                await refresh_soft_calls(conn)

        with timed("refresh"):
            await refresh_eval_impl(
                pool, redis,
                profile_id=profile_id, session_id=session_id,
                operation_key=idempotency_key,
            )

        return CreateEvalApiResponse(
            results=[
                EvalResultItem(
                    success=True,
                    eval_id=target_id,
                    message="Eval accepted" if accept else "Eval rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    has_errors = False
    error_results: list[EvalResultItem] = []

    with timed("resolve_values"):
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
        with timed("snapshot"):
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

    with timed("db_write"):
     async with pool.acquire() as conn:
        async with conn.transaction():
            for idx, item in enumerate(items):
                result = await create_eval_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=item.department_ids,
                    flag_ids=item.flag_ids or None,
                    model_ids=item.model_ids,
                    model_flag_ids=item.model_flag_ids,
                    model_rubric_ids=item.model_rubric_ids,
                    model_position_ids=item.model_position_ids,
                    eval_ids=[snapshot_ids[idx]] if snapshot_ids else None,
                    soft=soft,
                )

                # Pending ledger row tied to this tool call.
                if soft and idempotency_key is not None:
                    await create_soft_call(
                        conn,
                        redis,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="create",
                        artifact_id=result.id,
                    )

                results.append(
                    EvalResultItem(
                        success=True,
                        eval_id=result.id,
                        message=(
                            "Eval created (pending acceptance)"
                            if soft
                            else "Eval created successfully"
                        ),
                    )
                )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    if not soft:
        with timed("refresh"):
            await refresh_eval_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                soft=soft,
                operation_key=idempotency_key or (results[0].eval_id if results else None),
            )

        with timed("benchmark_sync"):
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
                    flag_ids=item.flag_ids or [],
                )
            except Exception as sync_err:
                logger.warning(f"sync_benchmark_entries failed (non-fatal): {sync_err}")

    # ── Hydrate full row content for the client ───────────────────────
    # See ``hydrate_eval_list_rows``: returns the same shape ``/eval/search``
    # does. Audit framework spreads response fields into the
    # ``eval.create.completed`` payload, so the client's ghost rail
    # materializes the new row directly — no SSR refresh.
    # Soft-pending creates skip hydration (dormant artifact stays).
    evals_payload = None
    if not soft:
        with timed("hydrate"):
            from app.infra.eval.hydrate_list_rows import hydrate_eval_list_rows

            new_ids = [
                r.eval_id for r in results if r.success and r.eval_id is not None
            ]
            if new_ids:
                evals_payload = await hydrate_eval_list_rows(
                    pool, redis, profile_id=profile_id, eval_ids=new_ids,
                )

    return CreateEvalApiResponse(
        results=results,
        idempotency_key=idempotency_key,
        evals=evals_payload,
    )
