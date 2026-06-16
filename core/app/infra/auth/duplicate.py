"""Auth duplicate logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.auth.permissions import compute_can_duplicate
from app.infra.auth.refresh import refresh_auth_impl
from app.infra.auth.types import DuplicateAuthApiResponse, ListAuthApiAuth
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.artifacts.auth.create import create_auth as create_auth_artifact
from app.tools.artifacts.auth.get import get_auths
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.utils.cache.hedged_row import transaction_with_writeback

ARTIFACT = "auth"


async def duplicate_auth_impl(
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
) -> DuplicateAuthApiResponse:
    """Duplicate an auth artifact."""
    auth_id = id  # alias: tools send 'id', internal code uses 'auth_id'
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

    if not compute_can_duplicate(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to duplicate this auth.",
        )

    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "duplicate":
            raise HTTPException(
                status_code=404,
                detail="No pending auth duplicate for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                async with transaction_with_writeback(conn):
                    await create_auth_artifact(conn, id=target_id, soft=False)

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                redis,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation="duplicate",
                artifact_id=target_id,
                status="accepted" if accept else "rejected",
            )
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

        await refresh_auth_impl(
            pool, redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )
        return DuplicateAuthApiResponse(
            success=True,
            auth_id=target_id,
            message="Auth duplicate accepted" if accept else "Auth duplicate rejected",
            idempotency_key=idempotency_key,
        )

    with timed("fetch_original"):
     async with pool.acquire() as conn:
        originals = await get_auths(
            conn,
            [auth_id],
            names=True,
            descriptions=True,
            departments=True,
            items=True,
            protocols=True,
            slugs=True,
            auths=True,
        )

    if not originals:
        raise HTTPException(
            status_code=404,
            detail=f"Auth {auth_id} not found.",
        )

    original = originals[0]

    with timed("new_name_and_flag"):
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
            flag_type="auth_active",
            auth=True,
            limit_count=10,
        )
        inactive_match = next((flag for flag in flag_results if not flag.value), None)
        if inactive_match:
            inactive_flag_id = inactive_match.id

    flag_ids = [inactive_flag_id] if inactive_flag_id else None

    with timed("db_write"):
     async with pool.acquire() as conn:
        async with transaction_with_writeback(conn):
            result = await create_auth_artifact(
                conn,
                id=idempotency_key,
                name_id=new_name_resource.id,
                description_id=original.description_ids[0] if original.description_ids else None,
                slug_id=original.slug_ids[0] if original.slug_ids else None,
                department_ids=original.department_ids,
                item_ids=original.item_ids,
                protocol_ids=original.protocol_ids,
                auth_ids=original.auth_ids,
                flag_ids=flag_ids,
                soft=soft,
            )

            if soft and idempotency_key is not None:
                await create_soft_call(
                    conn,
                    redis,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation="duplicate",
                    artifact_id=result.id,
                )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    if not soft:
        with timed("refresh"):
            await refresh_auth_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                operation_key=idempotency_key or result.id,
            )

    # Hydrate full row content for the client. See
    # ``hydrate_auth_list_rows``. Soft-pending duplicates skip
    # hydration: the dormant copy isn't fully active yet.
    auths_hydrated: list[ListAuthApiAuth] | None = None
    if not soft:
        from app.infra.auth.hydrate_list_rows import hydrate_auth_list_rows
        auths_hydrated = await hydrate_auth_list_rows(
            pool, redis, profile_id=profile_id, auth_ids=[result.id],
        )

    return DuplicateAuthApiResponse(
        success=True,
        auth_id=result.id,
        message=(
            "Auth duplicate accepted"
            if accept is not None and idempotency_key is not None
            else "Auth duplicated (pending acceptance)"
            if soft
            else f"Auth '{original_name}' duplicated successfully"
        ),
        idempotency_key=idempotency_key or result.id,
        auths=auths_hydrated,
    )
