"""Auth update logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.auth.permissions_context import (
    create_denormalized_snapshot,
    resolve_auth_permissions_context,
    resolve_auth_values,
)
from app.infra.auth.refresh import refresh_auth_impl
from app.infra.auth.types import UpdateAuthApiRequest, UpdateAuthApiResponse
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.auth.get import get_auths as get_auth_artifacts
from app.tools.artifacts.auth.update import _UNSET
from app.tools.artifacts.auth.update import update_auth as update_auth_artifact
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def update_auth_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdateAuthApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdateAuthApiResponse:
    """Auth bulk update using composable infra functions."""
    from app.infra.auth.permissions import compute_can_edit
    from app.infra.auth.types import AuthResultItem
    from app.infra.identity.keycloak_sync import perform_keycloak_sync

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    items = request.auths

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
            perms = await resolve_auth_permissions_context(conn, item.id)
            if not perms.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Auth {item.id} not found.",
                )
            if not compute_can_edit(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
                active_settings_count=perms.active_settings_count,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this auth.",
                )

    if accept is not None and idempotency_key is not None:
        if not accept:
            return UpdateAuthApiResponse(
                results=[
                    AuthResultItem(
                        success=True,
                        auth_id=item.id,
                        message="Update rejected",
                    )
                    for item in items
                ],
                idempotency_key=idempotency_key,
            )
        soft = False

    has_errors = False
    error_results: list[AuthResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_auth_values(conn, redis, item, is_create=False)
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
        return UpdateAuthApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    results: list[AuthResultItem] = []
    for item in items:
        async with pool.acquire() as conn:
            existing = await get_auth_artifacts(
                conn,
                [item.id],
                names=True,
                descriptions=True,
                departments=True,
                slugs=True,
                protocols=True,
            )

        auths_resource_id = None
        if not soft:
            if existing:
                artifact = existing[0]
                eff_name_id = item.name_id or (artifact.name_ids[0] if artifact.name_ids else None)
                eff_description_id = item.description_id or (artifact.description_ids[0] if artifact.description_ids else None)
                eff_department_ids = (
                    item.department_ids if item.department_ids is not None else list(artifact.department_ids or [])
                )
                eff_slug_id = item.slug_id or (artifact.slug_ids[0] if artifact.slug_ids else None)
                eff_protocol_ids = (
                    item.protocol_ids if item.protocol_ids is not None else list(artifact.protocol_ids or [])
                )
            else:
                eff_name_id = item.name_id
                eff_description_id = item.description_id
                eff_department_ids = item.department_ids
                eff_slug_id = item.slug_id
                eff_protocol_ids = item.protocol_ids

            auths_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                name_id=eff_name_id,
                description_id=eff_description_id,
                department_ids=eff_department_ids,
                slug_id=eff_slug_id,
                protocol_ids=eff_protocol_ids,
            )

        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_auth_artifact(
                    conn,
                    item.id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id if item.description_id else _UNSET,
                    slug_id=item.slug_id if item.slug_id else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=item.flag_ids or None,
                    item_ids=item.item_ids,
                    protocol_ids=item.protocol_ids,
                    auth_ids=[auths_resource_id] if auths_resource_id else item.auth_resource_ids,
                    soft=soft,
                )

        results.append(
            AuthResultItem(
                success=True,
                auth_id=item.id,
                message=(
                    "Auth update accepted"
                    if accept is not None and idempotency_key is not None
                    else "Auth updated (pending acceptance)"
                    if soft
                    else "Auth updated successfully"
                ),
            )
        )

    if not soft:
        await refresh_auth_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (results[0].auth_id if results else None),
        )

        try:
            await perform_keycloak_sync(department_id=None)
        except Exception:
            logger.warning("Keycloak sync failed after auth update (non-fatal)")

    return UpdateAuthApiResponse(
        results=results,
        idempotency_key=idempotency_key,
    )
