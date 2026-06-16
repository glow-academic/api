"""Department create logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.department.permissions_context import (
    create_denormalized_snapshot,
    resolve_department_values,
)
from app.infra.department.refresh import refresh_department_impl
from app.infra.department.types import (
    CreateDepartmentApiRequest,
    CreateDepartmentApiResponse,
    DepartmentResultItem,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.artifacts.department.create import (
    create_department as create_department_artifact,
)
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.utils.logging.db_logger import get_logger
from app.utils.cache.hedged_row import transaction_with_writeback

logger = get_logger(__name__)

ARTIFACT = "department"

_KEYCLOAK_CREATE_SYNC_WARNING = (
    " (warning: identity-provider sync to Keycloak did not complete — login "
    "scoped to this department may not work until Keycloak is reachable and "
    "re-syncs)"
)


async def create_department_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: CreateDepartmentApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> CreateDepartmentApiResponse:
    """Department bulk create using composable infra functions."""
    from app.infra.department.permissions import compute_can_create
    from app.infra.identity.keycloak_sync import perform_keycloak_sync

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    items = request.departments
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
                detail="You don't have permission to create departments.",
            )

    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "create":
            raise HTTPException(
                status_code=404,
                detail="No pending department create for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                async with transaction_with_writeback(conn):
                    await create_department_artifact(conn, id=target_id, soft=False)

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

        await refresh_department_impl(
            pool, redis,
            profile_id=profile_id,
            session_id=session_id,
            operation_key=idempotency_key,
        )
        return CreateDepartmentApiResponse(
            results=[
                DepartmentResultItem(
                    success=True,
                    department_id=target_id,
                    message="Department accepted" if accept else "Department rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    has_errors = False
    error_results: list[DepartmentResultItem] = []

    with timed("resolve_values"):
     async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_department_values(conn, redis, item, is_create=True)
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
        return CreateDepartmentApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    results: list[DepartmentResultItem] = []
    saved_department_ids: list[UUID] = []
    snapshot_ids: list[UUID] = []

    if not soft:
      with timed("snapshot"):
        for item in items:
            departments_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                id=item.resource_id,
                name_id=item.name_id,
                description_id=item.description_id,
                setting_ids=item.settings_ids,
            )
            snapshot_ids.append(departments_resource_id)

    with timed("db_write"):
     async with pool.acquire() as conn:
        async with transaction_with_writeback(conn):
            for idx, item in enumerate(items):
                result = await create_department_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=[snapshot_ids[idx]] if snapshot_ids else None,
                    flag_ids=list(item.flag_ids) if item.flag_ids else None,
                    settings_ids=item.settings_ids,
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

                saved_department_ids.append(result.id)
                results.append(
                    DepartmentResultItem(
                        success=True,
                        department_id=result.id,
                        message=(
                            "Department accepted"
                            if accept is not None and idempotency_key is not None
                            else "Department created (pending acceptance)"
                            if soft
                            else "Department created successfully"
                        ),
                    )
                )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    if not soft:
        with timed("refresh"):
            await refresh_department_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                soft=soft,
                operation_key=idempotency_key or (results[0].department_id if results else None),
            )

        # Provision each new department's Keycloak IdP scope. The DB rows are
        # committed, but until the sync lands the department isn't reflected in
        # Keycloak, so a failure is NOT cosmetic. ``perform_keycloak_sync`` does
        # NOT raise on failure — it returns ``KeycloakSyncResult(success=False)``
        # and logs internally, so the old ``except Exception`` was dead code and
        # the ``False`` result was dropped while results still said "created
        # successfully". Surface it per-department (mirrors #249).
        failed_sync_ids: set[UUID] = set()
        for department_id in saved_department_ids:
            try:
                sync_result = await perform_keycloak_sync(department_id=str(department_id))
            except Exception as e:  # defensive — perform_* shouldn't raise
                logger.warning(
                    f"Keycloak sync errored after department {department_id} create: {e}"
                )
                sync_result = None
            if sync_result is None or not sync_result.success:
                failed_sync_ids.add(department_id)
                detail = sync_result.message if sync_result else "Keycloak sync errored"
                logger.warning(
                    f"Keycloak sync did not complete after department "
                    f"{department_id} create: {detail}"
                )
        if failed_sync_ids:
            for result_item in results:
                if result_item.success and result_item.department_id in failed_sync_ids:
                    result_item.message += _KEYCLOAK_CREATE_SYNC_WARNING

    # ── Hydrate full row content for the client ───────────────────────
    # See ``hydrate_department_list_rows``: returns the same shape
    # ``/department/search`` does. Audit framework spreads response
    # fields into ``department.create.completed``, so the client's
    # ghost rail materializes the new row directly — no SSR refresh.
    # Soft-pending creates skip hydration: the dormant row isn't fully
    # active yet (denormalized snapshot is created on ack-accept).
    departments_payload = None
    if not soft:
        from app.infra.department.hydrate_list_rows import (
            hydrate_department_list_rows,
        )
        new_ids = [r.department_id for r in results if r.success and r.department_id is not None]
        if new_ids:
            departments_payload = await hydrate_department_list_rows(
                pool, redis, profile_id=profile_id, department_ids=new_ids,
            )

    return CreateDepartmentApiResponse(
        results=results,
        idempotency_key=idempotency_key,
        departments=departments_payload,
    )
