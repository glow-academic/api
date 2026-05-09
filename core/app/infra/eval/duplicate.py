"""Eval duplicate logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.eval.permissions import compute_can_duplicate
from app.infra.eval.refresh import refresh_eval_impl
from app.infra.eval.types import DuplicateEvalApiResponse
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.eval.create import create_eval as create_eval_artifact
from app.tools.artifacts.eval.get import get_evals
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names

ARTIFACT = "eval"


async def duplicate_eval_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    id: UUID,
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **_kwargs,
) -> DuplicateEvalApiResponse:
    """Duplicate an eval artifact."""
    eval_id = id  # alias: tools send 'id', internal code uses 'eval_id'
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

    if not compute_can_duplicate(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to duplicate this eval.",
        )

    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "duplicate":
            raise HTTPException(
                status_code=404,
                detail="No pending eval duplicate for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await create_eval_artifact(conn, id=target_id, soft=False)

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation="duplicate",
                artifact_id=target_id,
                status="accepted" if accept else "rejected",
            )
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

        await refresh_eval_impl(
            pool, redis,
            profile_id=profile_id, session_id=session_id,
            operation_key=idempotency_key,
        )

        return DuplicateEvalApiResponse(
            success=True,
            eval_id=target_id,
            message="Eval duplicate accepted" if accept else "Eval duplicate rejected",
            idempotency_key=idempotency_key,
        )

    async with pool.acquire() as conn:
        originals = await get_evals(
            conn,
            [eval_id],
            names=True,
            descriptions=True,
            departments=True,
            models=True,
            model_flags=True,
            model_positions=True,
            model_rubrics=True,
            evals=True,
        )

    if not originals:
        raise HTTPException(
            status_code=404,
            detail=f"Eval {eval_id} not found.",
        )

    original = originals[0]

    async with pool.acquire() as conn:
        original_name = "Unknown"
        if original.name_ids:
            name_resources = await get_names(pool, original.name_ids, redis)
            if name_resources:
                original_name = name_resources[0].name or "Unknown"

        new_name_resource = await create_name(conn, f"{original_name} Copy", redis)

        inactive_flag_id: UUID | None = None
        flag_results = await search_flags(
            conn,
            redis,
            flag_type="eval_active",
            eval=True,
            limit_count=10,
        )
        inactive_match = next((flag for flag in flag_results if not flag.value), None)
        if inactive_match:
            inactive_flag_id = inactive_match.id

    flag_ids = [inactive_flag_id] if inactive_flag_id else None

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_eval_artifact(
                conn,
                id=idempotency_key,
                name_id=new_name_resource.id,
                description_id=original.description_ids[0] if original.description_ids else None,
                department_ids=original.department_ids,
                model_ids=original.model_ids,
                model_flag_ids=original.model_flag_ids,
                model_position_ids=original.model_position_ids,
                model_rubric_ids=original.model_rubric_ids,
                eval_ids=original.eval_ids,
                flag_ids=flag_ids,
                soft=soft,
            )

            # Pending ledger row tied to this tool call.
            if soft and idempotency_key is not None:
                await create_soft_call(
                    conn,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation="duplicate",
                    artifact_id=result.id,
                )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    if not soft:
        await refresh_eval_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key or result.id,
        )

    # ── Hydrate full row content for the client ───────────────────────
    # Single-element list — duplicate creates exactly one row, but the
    # wire shape stays a list for consistency with create/update.
    evals_payload = None
    if not soft:
        from app.infra.eval.hydrate_list_rows import hydrate_eval_list_rows

        evals_payload = await hydrate_eval_list_rows(
            pool, redis, profile_id=profile_id, eval_ids=[result.id],
        )

    return DuplicateEvalApiResponse(
        success=True,
        eval_id=result.id,
        message=(
            "Eval duplicate accepted"
            if accept is not None and idempotency_key is not None
            else "Eval duplicated (pending acceptance)"
            if soft
            else f"Eval '{original_name}' duplicated successfully"
        ),
        idempotency_key=idempotency_key or result.id,
        evals=evals_payload,
    )
