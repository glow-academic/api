"""Department update logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.department.permissions_context import (
    create_denormalized_snapshot,
    resolve_department_permissions_context,
    resolve_department_values,
)
from app.infra.department.refresh import refresh_department_impl
from app.infra.department.types import (
    UpdateDepartmentApiRequest,
    UpdateDepartmentApiResponse,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.department.get import (
    get_departments as get_department_artifacts,
)
from app.tools.artifacts.department.update import (
    _UNSET,
)
from app.tools.artifacts.department.update import (
    update_department as update_department_artifact,
)
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls

ARTIFACT = "department"


async def update_department_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdateDepartmentApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdateDepartmentApiResponse:
    """Department bulk update using composable infra functions.

    Three call shapes:
      - First call (explicit): ``request.departments`` required.
      - First call (all-matching): ``request.all=true`` plus ``patch``
        plus filter fields. The impl resolves matching ids, clones
        the patch per id (stamping each id), then runs the existing
        per-row update flow. Per-row permission failures soft-skip.
      - Ack call: ``idempotency_key`` + ``accept`` only.
    """
    from app.infra.department.permissions import compute_can_edit
    from app.infra.department.types import DepartmentResultItem
    from app.infra.identity.keycloak_sync import perform_keycloak_sync

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    # ── ACK short-circuit ──────────────────────────────────────────────
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "update":
            raise HTTPException(
                status_code=404,
                detail="No pending department update for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await update_department_artifact(conn, target_id, soft=False)

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                redis,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation="update",
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
        return UpdateDepartmentApiResponse(
            results=[
                DepartmentResultItem(
                    success=True,
                    department_id=target_id,
                    message="Update accepted" if accept else "Update rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── All-matching path: resolve ids + synthesize per-row items ─────
    # Past the ack short-circuit and ``all=true`` ⇒ enumerate every
    # department matching the filter, then clone ``request.patch`` per
    # id (stamping the resolved id). The downstream per-row flow runs
    # unchanged. Per-row permission failures soft-skip (collected into
    # ``skipped_results`` and threaded into the final response).
    skipped_results: list[DepartmentResultItem] = []

    if request.all:
        if request.patch is None:
            raise HTTPException(
                status_code=400,
                detail="`patch` is required when `all=true` "
                "(it carries the shared change set applied to every matched row).",
            )
        from app.infra.department.resolve_matching_ids import (
            resolve_matching_department_ids,
        )
        from app.infra.department.types import UpdateDepartmentItem

        matching = await resolve_matching_department_ids(
            pool, redis,
            profile_id=profile_id,
            search=request.search,
            flag_search=request.flag_search,
        )
        excluded = set(request.excluded_ids or [])
        resolved_ids = [did for did in matching if did not in excluded]

        if not resolved_ids:
            return UpdateDepartmentApiResponse(results=[], idempotency_key=idempotency_key)

        # Clone the patch per matched row, stamping the resolved id.
        # ``model_dump(exclude_unset=True, exclude={"id"})`` keeps sparse
        # semantics — only fields the client actually set are written.
        patch_fields = request.patch.model_dump(exclude_unset=True, exclude={"id"})
        synth_items = [UpdateDepartmentItem(id=did, **patch_fields) for did in resolved_ids]
        request = request.model_copy(update={"departments": synth_items})

    # ── First-call requirements ───────────────────────────────────────
    if not request.departments:
        raise HTTPException(
            status_code=400,
            detail="`request.departments` is required for first-call update "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with `patch` and filter fields).",
        )

    items = request.departments

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

    # ── Per-item permission check ──────────────────────────────────────
    # Explicit path fails fast (existing behavior).
    # All-matching path soft-skips so the response carries per-row
    # outcomes without aborting rows the user CAN edit.
    is_all_matching = bool(request.all)
    permitted_items: list = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            perms = await resolve_department_permissions_context(conn, item.id)
            if not perms.exists:
                if is_all_matching:
                    skipped_results.append(DepartmentResultItem(
                        success=False, department_id=item.id,
                        message=f"Department {item.id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Department {item.id} not found.",
                )
            if not compute_can_edit(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
                usage_count=perms.usage_count,
            ):
                if is_all_matching:
                    skipped_results.append(DepartmentResultItem(
                        success=False, department_id=item.id,
                        message=f"No permission to update department {item.id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this department.",
                )

            permitted_items.append(item)

    if is_all_matching:
        items = permitted_items
        if not items:
            return UpdateDepartmentApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    has_errors = False
    error_results: list[DepartmentResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_department_values(conn, redis, item, is_create=False)
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
        return UpdateDepartmentApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    results: list[DepartmentResultItem] = []
    saved_department_ids: list[UUID] = []

    for item in items:
        async with pool.acquire() as conn:
            existing = await get_department_artifacts(
                conn,
                [item.id],
                names=True,
                descriptions=True,
                settings=True,
            )

        departments_resource_id = None
        if not soft:
            if existing:
                art = existing[0]
                eff_name_id = item.name_id or (art.name_ids[0] if art.name_ids else None)
                eff_desc_id = item.description_id or (art.description_ids[0] if art.description_ids else None)
                eff_setting_ids = item.settings_ids if item.settings_ids is not None else list(art.settings_ids or [])
            else:
                eff_name_id = item.name_id
                eff_desc_id = item.description_id
                eff_setting_ids = item.settings_ids

            departments_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                name_id=eff_name_id,
                description_id=eff_desc_id,
                setting_ids=eff_setting_ids,
            )

        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_department_artifact(
                    conn,
                    item.id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id if item.description_id else _UNSET,
                    department_ids=[departments_resource_id] if departments_resource_id else None,
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
                        operation="update",
                        artifact_id=item.id,
                    )

        saved_department_ids.append(item.id)
        results.append(
            DepartmentResultItem(
                success=True,
                department_id=item.id,
                message=(
                    "Department update accepted"
                    if accept is not None and idempotency_key is not None
                    else "Department updated (pending acceptance)"
                    if soft
                    else "Department updated successfully"
                ),
            )
        )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    if not soft:
        await refresh_department_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (results[0].department_id if results else None),
        )

        for department_id in saved_department_ids:
            try:
                await perform_keycloak_sync(department_id=str(department_id))
            except Exception:
                pass

    # ── Hydrate full row content for the client ───────────────────────
    # See ``hydrate_department_list_rows``: returns the same shape
    # ``/department/search`` does. Audit framework spreads response
    # fields into ``department.update.completed``, so the client's
    # ghost rail materializes the changed row directly — no SSR refresh.
    # Soft-pending updates skip hydration (dormant artifact stays).
    departments_payload = None
    if not soft:
        from app.infra.department.hydrate_list_rows import (
            hydrate_department_list_rows,
        )
        updated_ids = [
            r.department_id for r in results
            if r.success and r.department_id is not None
        ]
        if updated_ids:
            departments_payload = await hydrate_department_list_rows(
                pool, redis, profile_id=profile_id, department_ids=updated_ids,
            )

    # All-matching path threads soft-skipped rows back into the
    # response so the client can surface "X updated, Y skipped" in
    # one toast. Explicit path's ``skipped_results`` is empty.
    return UpdateDepartmentApiResponse(
        results=results + skipped_results,
        idempotency_key=idempotency_key,
        departments=departments_payload,
    )
