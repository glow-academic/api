"""Auth create logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.auth.permissions_context import (
    create_denormalized_snapshot,
    resolve_auth_values,
)
from app.infra.auth.refresh import refresh_auth_impl
from app.infra.auth.types import (
    AuthResultItem,
    CreateAuthApiRequest,
    CreateAuthApiResponse,
    ListAuthApiAuth,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.artifacts.auth.create import create_auth as create_auth_artifact
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.utils.logging.db_logger import get_logger
from app.utils.cache.hedged_row import transaction_with_writeback

logger = get_logger(__name__)

ARTIFACT = "auth"


async def create_auth_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: CreateAuthApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> CreateAuthApiResponse:
    """Auth bulk create using composable infra functions."""
    from app.infra.auth.permissions import compute_can_create
    from app.infra.identity.keycloak_sync import perform_keycloak_sync
    from app.utils.async_tasks import schedule_background

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    items = request.auths or []
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

    if not compute_can_create(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create auths.",
        )

    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "create":
            raise HTTPException(
                status_code=404,
                detail="No pending auth create for this call.",
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
                operation="create",
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
        return CreateAuthApiResponse(
            results=[
                AuthResultItem(
                    success=True,
                    auth_id=target_id,
                    message="Auth accepted" if accept else "Auth rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    has_errors = False
    error_results: list[AuthResultItem] = []

    with timed("resolve_values"):
     async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_auth_values(conn, redis, item, is_create=True)
            if item_errors:
                has_errors = True
                error_results.append(
                    AuthResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(AuthResultItem(success=True, message="Validated"))

    if has_errors:
        return CreateAuthApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    results: list[AuthResultItem] = []
    snapshot_ids: list[UUID] = []

    if not soft:
        for item in items:
            auths_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                id=item.resource_id,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                slug_id=item.slug_id,
                protocol_ids=item.protocol_ids,
            )
            snapshot_ids.append(auths_resource_id)

    with timed("db_write"):
     async with pool.acquire() as conn:
        async with transaction_with_writeback(conn):
            for idx, item in enumerate(items):
                result = await create_auth_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    slug_id=item.slug_id,
                    department_ids=item.department_ids,
                    flag_ids=item.flag_ids or None,
                    item_ids=item.item_ids,
                    protocol_ids=item.protocol_ids,
                    auth_ids=[snapshot_ids[idx]] if snapshot_ids else item.auth_resource_ids,
                    soft=soft,
                )

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
                    AuthResultItem(
                        success=True,
                        auth_id=result.id,
                        message=(
                            "Auth accepted"
                            if accept is not None and idempotency_key is not None
                            else "Auth created (pending acceptance)"
                            if soft
                            else "Auth created successfully"
                        ),
                    )
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
                soft=soft,
                operation_key=idempotency_key or (results[0].auth_id if results else None),
            )

        # Provision the new auth provider as a Keycloak IdP — but do NOT block
        # the HTTP response on it. The auth row is already committed (and is
        # immediately visible via /auth/search); the Keycloak IdP sync is a
        # best-effort post-write side effect.
        #
        # Why fire-and-forget: ``perform_keycloak_sync`` can be slow or stall
        # for a long time — most notably the fresh-deploy Keycloak sync-race,
        # where the admin client is briefly ``unauthorized_client`` and the
        # sync retries for ~90-150s. Awaiting it inline pushed /auth/create
        # past nginx's 60s ``proxy_read_timeout`` → a 504 to the caller, EVEN
        # THOUGH the auth row had already been written. That 504 broke the
        # auths-create / auths-bulk demos.
        #
        # The sync still HAPPENS (it is not dropped) — it just runs off the
        # response critical path. ``perform_keycloak_sync`` is idempotent
        # (every ``ensure_*`` upserts) and does not raise on failure; any error
        # is logged by ``schedule_background`` under the label below and the
        # backstop ``schedule_keycloak_resync`` reconciles later. So KC
        # eventually reflects the new auth without ever blocking the create.
        schedule_background(
            perform_keycloak_sync(department_id=None),
            label="auth_create_kc_idp_sync",
        )

    # Hydrate full row content for the client. See
    # ``hydrate_auth_list_rows``: returns the same shape /auth/search
    # does. Audit framework spreads response fields into
    # ``auth.create.completed``, so the client's ghost rail materializes
    # the new row directly — no SSR refresh round-trip. Soft-pending
    # creates skip hydration: the dormant row isn't fully active yet.
    auths_hydrated: list[ListAuthApiAuth] | None = None
    if not soft:
        with timed("hydrate"):
            from app.infra.auth.hydrate_list_rows import hydrate_auth_list_rows
            new_ids = [r.auth_id for r in results if r.success and r.auth_id is not None]
            if new_ids:
                auths_hydrated = await hydrate_auth_list_rows(
                    pool, redis, profile_id=profile_id, auth_ids=new_ids,
                )

    return CreateAuthApiResponse(
        results=results,
        idempotency_key=idempotency_key,
        auths=auths_hydrated,
    )
