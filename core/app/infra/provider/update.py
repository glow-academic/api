"""Provider update logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.infra.provider.permissions_context import (
    create_denormalized_snapshot,
    resolve_provider_permissions_context,
    resolve_provider_values,
)
from app.infra.provider.refresh import refresh_provider_impl
from app.infra.provider.types import (
    ListProviderApiProvider,
    UpdateProviderApiRequest,
    UpdateProviderApiResponse,
)
from app.tools.artifacts.provider.update import _UNSET
from app.tools.artifacts.provider.update import (
    update_provider as update_provider_artifact,
)
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls

ARTIFACT = "provider"


async def update_provider_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdateProviderApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdateProviderApiResponse:
    """Provider bulk update using composable infra functions.

    Three call shapes:
      - First call (explicit): ``request.providers`` required.
      - First call (all-matching): ``request.all=true`` plus ``patch``
        plus filter fields. The impl resolves matching ids, clones the
        patch per id (stamping each id), then runs the existing per-row
        update flow. Per-row permission failures soft-skip.
      - Ack call: ``idempotency_key`` + ``accept`` only.
    """
    from app.infra.provider.permissions import compute_can_edit
    from app.infra.provider.types import ProviderResultItem

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    # ── Short-circuit: ack path ───────────────────────────────────────
    # Hoisted above per-row perm checks because under ack/all paths
    # ``request.providers`` is None and the perm loop would explode.
    # The dormant row is located by ``idempotency_key``.
    if accept is not None and idempotency_key is not None:
        with timed("ack"):
            async with pool.acquire() as conn:
                entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
            if entry is None or entry.status != "pending" or entry.operation != "update":
                raise HTTPException(
                    status_code=404,
                    detail="No pending provider update for this call.",
                )
            target_id = entry.artifact_id

            if accept:
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        await update_provider_artifact(
                            conn,
                            target_id,
                            soft=False,
                        )

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

        with timed("refresh"):
            await refresh_provider_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                operation_key=idempotency_key,
            )

        return UpdateProviderApiResponse(
            results=[
                ProviderResultItem(
                    success=True,
                    provider_id=target_id,
                    message="Update accepted" if accept else "Update rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── All-matching path: resolve ids + synthesize per-row items ─────
    # Past the ack short-circuit and ``all=true`` ⇒ enumerate every
    # provider matching the filter, then clone ``request.patch`` per
    # id (stamping the resolved id). The downstream per-row flow runs
    # unchanged. Per-row permission failures soft-skip.
    skipped_results: list[ProviderResultItem] = []

    if request.all:
        if request.patch is None:
            raise HTTPException(
                status_code=400,
                detail="`patch` is required when `all=true` "
                "(it carries the shared change set applied to every matched row).",
            )
        from app.infra.provider.resolve_matching_ids import (
            resolve_matching_provider_ids,
        )
        from app.infra.provider.types import UpdateProviderItem

        matching = await resolve_matching_provider_ids(
            pool, redis,
            profile_id=profile_id,
            search=request.search,
            filter_department_ids=request.filter_department_ids,
            filter_model_ids=request.filter_model_ids,
            filter_status=request.filter_status,
            department_search=request.department_search,
            model_search=request.model_search,
            flag_search=request.flag_search,
        )
        excluded = set(request.excluded_ids or [])
        resolved_ids = [pid for pid in matching if pid not in excluded]

        if not resolved_ids:
            return UpdateProviderApiResponse(
                results=[], idempotency_key=idempotency_key,
            )

        # Clone the patch per matched row, stamping the resolved id.
        # ``model_dump(exclude_unset=True, exclude={"id"})`` keeps
        # sparse semantics — only fields the client actually set are
        # written.
        patch_fields = request.patch.model_dump(exclude_unset=True, exclude={"id"})
        synth_items = [UpdateProviderItem(id=pid, **patch_fields) for pid in resolved_ids]
        request = request.model_copy(update={"providers": synth_items})

    # ── First-call requirements ───────────────────────────────────────
    if not request.providers:
        raise HTTPException(
            status_code=400,
            detail="`request.providers` is required for first-call update "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with `patch` and filter fields).",
        )

    items = request.providers

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

    # ── Per-item permission check ─────────────────────────────────────
    # Explicit path fails fast (existing behavior).
    # All-matching path soft-skips so the response carries per-row
    # outcomes without aborting rows the user CAN edit.
    is_all_matching = bool(request.all)
    permitted_items: list = []

    with timed("permissions"):
     async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            perms = await resolve_provider_permissions_context(conn, item.id)
            if not perms.exists:
                if is_all_matching:
                    skipped_results.append(ProviderResultItem(
                        success=False, provider_id=item.id,
                        message=f"Provider {item.id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Provider {item.id} not found.",
                )
            if not compute_can_edit(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
                provider_department_ids=perms.department_ids,
                active_model_count=perms.active_model_count,
                user_department_ids=profile.department_ids,
            ):
                if is_all_matching:
                    skipped_results.append(ProviderResultItem(
                        success=False, provider_id=item.id,
                        message=f"No permission to update provider {item.id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this provider.",
                )
            permitted_items.append(item)

    if is_all_matching:
        items = permitted_items
        if not items:
            return UpdateProviderApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    has_errors = False
    error_results: list[ProviderResultItem] = []

    with timed("resolve_values"):
     async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_provider_values(
                conn,
                redis,
                item,
                is_create=False,
            )
            if item_errors:
                has_errors = True
                error_results.append(
                    ProviderResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(ProviderResultItem(success=True, message="Validated"))

    if has_errors:
        return UpdateProviderApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    results: list[ProviderResultItem] = []

    with timed("db_write"):
     for item in items:
        providers_resource_id = None
        if not soft:
            providers_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
            )

        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_provider_artifact(
                    conn,
                    item.id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id if item.description_id else _UNSET,
                    department_ids=item.department_ids,
                    endpoint_ids=item.endpoint_ids,
                    flag_ids=item.flag_ids or None,
                    key_ids=item.key_ids,
                    provider_ids=[providers_resource_id] if providers_resource_id else None,
                    value_id=item.value_id,
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

        results.append(
            ProviderResultItem(
                success=True,
                provider_id=item.id,
                message="Provider updated (pending acceptance)" if soft else "Provider updated successfully",
            )
        )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    if not soft:
        with timed("refresh"):
            await refresh_provider_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                soft=soft,
                operation_key=idempotency_key or (results[0].provider_id if results else None),
            )

    # ── Hydrate full row content for the client ──────────────────────
    # See ``hydrate_provider_list_rows``. Soft-pending updates skip
    # hydration: the dormant change isn't visible in the active row
    # yet (artifact is deactivated until ack-accept promotes it).
    providers: list[ListProviderApiProvider] | None = None
    if not soft:
        with timed("hydrate"):
            from app.infra.provider.hydrate_list_rows import hydrate_provider_list_rows
            updated_ids = [r.provider_id for r in results if r.success and r.provider_id is not None]
            if updated_ids:
                providers = await hydrate_provider_list_rows(
                    pool, redis, profile_id=profile_id, provider_ids=updated_ids,
                )

    # All-matching path threads soft-skipped rows back into the
    # response so the client can surface "X updated, Y skipped" in
    # one toast. Explicit path's ``skipped_results`` is empty.
    return UpdateProviderApiResponse(
        results=results + skipped_results,
        idempotency_key=idempotency_key,
        providers=providers,
    )
