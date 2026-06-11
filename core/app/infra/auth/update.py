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
from app.infra.auth.types import (
    ListAuthApiAuth,
    UpdateAuthApiRequest,
    UpdateAuthApiResponse,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.artifacts.auth.get import get_auths as get_auth_artifacts
from app.tools.artifacts.auth.update import _UNSET
from app.tools.artifacts.auth.update import update_auth as update_auth_artifact
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.entries.soft_calls.resolve import resolve_soft_call
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

ARTIFACT = "auth"


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
    """Auth bulk update using composable infra functions.

    Three call shapes:
      - First call (explicit): ``request.auths`` required.
      - First call (all-matching): ``request.all=true`` plus ``patch``
        plus filter fields. The impl resolves matching ids, clones
        the patch per id (stamping each id), then runs the existing
        per-row update flow. Per-row permission failures soft-skip.
      - Ack call: ``idempotency_key`` + ``accept`` only.
    """
    from app.infra.auth.permissions import compute_can_edit
    from app.infra.auth.types import AuthResultItem
    from app.infra.identity.keycloak_sync import perform_keycloak_sync

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    # ── Short-circuit: ack path ───────────────────────────────────────
    # Hoisted above perm checks so ack/all paths don't trip on
    # ``request.auths`` being None.
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "update":
            raise HTTPException(
                status_code=404,
                detail="No pending auth update for this call.",
            )
        target_id = entry.artifact_id

        # ── Atomic ack (A3/A4) ────────────────────────────────────────────
        # One transaction: the conditional terminal-state transition
        # (resolve_soft_call) + the row re-activation commit together. A
        # concurrent double-ack loses the race → resolve returns None → we SKIP
        # the re-activation (no double side effect). A crash before commit
        # rolls back BOTH the activation and the ledger row. The soft-call MV
        # refresh + auth refresh run only AFTER the commit.
        async with pool.acquire() as conn:
            async with conn.transaction():
                resolved = await resolve_soft_call(
                    conn,
                    redis,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation="update",
                    artifact_id=target_id,
                    accept=accept,
                )
                already_resolved = resolved is None
                if not already_resolved and accept:
                    # Re-activate the row. The soft (propose) write flipped
                    # ``active=False`` (soft forces it), which hides the row
                    # from ``search_auth`` (filters ``a.active = true``). The
                    # accept must explicitly set ``active=True`` — without it
                    # the tool's else-branch only touches ``updated_at``/``mcp``
                    # and the accepted change stays invisible forever. Mirrors
                    # the attempt start/complete ack reactivation paths.
                    await update_auth_artifact(
                        conn, target_id, active=True, soft=False
                    )

        if not already_resolved:
            async with pool.acquire() as conn:
                await refresh_soft_calls(conn)

            await refresh_auth_impl(
                pool, redis,
                profile_id=profile_id,
                session_id=session_id,
                operation_key=idempotency_key,
            )
        return UpdateAuthApiResponse(
            results=[
                AuthResultItem(
                    success=True,
                    auth_id=target_id,
                    message="Update accepted" if accept else "Update rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── All-matching path: resolve ids + synthesize per-row items ─────
    skipped_results: list[AuthResultItem] = []

    if request.all:
        if request.patch is None:
            raise HTTPException(
                status_code=400,
                detail="`patch` is required when `all=true` "
                "(it carries the shared change set applied to every matched row).",
            )
        from app.infra.auth.resolve_matching_ids import resolve_matching_auth_ids
        from app.infra.auth.types import UpdateAuthItem

        matching = await resolve_matching_auth_ids(
            pool, redis,
            profile_id=profile_id,
            search=request.search,
            filter_department_ids=request.filter_department_ids,
            department_search=request.department_search,
            flag_search=request.flag_search,
        )
        excluded = set(request.excluded_ids or [])
        resolved_ids = [aid for aid in matching if aid not in excluded]

        if not resolved_ids:
            return UpdateAuthApiResponse(results=[], idempotency_key=idempotency_key)

        patch_fields = request.patch.model_dump(exclude_unset=True, exclude={"id"})
        synth_items = [UpdateAuthItem(id=aid, **patch_fields) for aid in resolved_ids]
        request = request.model_copy(update={"auths": synth_items})

    # ── First-call requirements ───────────────────────────────────────
    if not request.auths:
        raise HTTPException(
            status_code=400,
            detail="`request.auths` is required for first-call update "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with `patch` and filter fields).",
        )

    items = request.auths

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
    # Explicit path fails fast; all-matching path soft-skips so the
    # response carries per-row outcomes without aborting rows the user
    # CAN edit.
    is_all_matching = bool(request.all)
    permitted_items: list = []

    with timed("permissions"):
     async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            perms = await resolve_auth_permissions_context(conn, item.id)
            if not perms.exists:
                if is_all_matching:
                    skipped_results.append(AuthResultItem(
                        success=False, auth_id=item.id,
                        message=f"Auth {item.id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Auth {item.id} not found.",
                )
            if not compute_can_edit(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
                active_settings_count=perms.active_settings_count,
            ):
                if is_all_matching:
                    skipped_results.append(AuthResultItem(
                        success=False, auth_id=item.id,
                        message=f"No permission to update auth {item.id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this auth.",
                )
            permitted_items.append(item)

    if is_all_matching:
        items = permitted_items
        if not items:
            return UpdateAuthApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    # ── Per-item value resolution ─────────────────────────────────────
    has_errors = False
    error_results: list[AuthResultItem] = []

    with timed("resolve_values"):
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

    # ── Per-item update ───────────────────────────────────────────────
    results: list[AuthResultItem] = []
    with timed("db_write"):
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

        # Re-sync the auth provider's Keycloak IdP after the update. The DB
        # row is already committed, but until this sync lands the provider's
        # IdP config in Keycloak is stale, so login through it may not reflect
        # the change (or work at all). A failure here is NOT cosmetic.
        #
        # NOTE: ``perform_keycloak_sync`` does NOT raise on failure (e.g.
        # Keycloak unreachable); it returns ``KeycloakSyncResult(success=False)``
        # and logs internally. The old ``except Exception`` here was therefore
        # dead code that never fired, and the real failure (a ``False`` result)
        # was dropped while every ``AuthResultItem`` still said "Auth updated
        # successfully". Surface it instead — mirrors #249's create fix.
        try:
            sync_result = await perform_keycloak_sync(department_id=None)
        except Exception as e:  # defensive — perform_* shouldn't raise
            logger.warning(f"Keycloak sync errored after auth update: {e}")
            sync_result = None
        if sync_result is None or not sync_result.success:
            detail = sync_result.message if sync_result else "Keycloak sync errored"
            logger.warning(
                f"Keycloak sync did not complete after auth update: {detail}"
            )
            for result_item in results:
                if result_item.success:
                    result_item.message += (
                        " (warning: identity-provider sync to Keycloak did not "
                        "complete — login via this provider may not work until "
                        "Keycloak is reachable and re-syncs)"
                    )

    # Hydrate full row content for the client. See
    # ``hydrate_auth_list_rows``. Soft-pending updates skip hydration:
    # the dormant change isn't visible in the active row yet.
    auths_hydrated: list[ListAuthApiAuth] | None = None
    if not soft:
        from app.infra.auth.hydrate_list_rows import hydrate_auth_list_rows
        updated_ids = [r.auth_id for r in results if r.success and r.auth_id is not None]
        if updated_ids:
            auths_hydrated = await hydrate_auth_list_rows(
                pool, redis, profile_id=profile_id, auth_ids=updated_ids,
            )

    # All-matching path threads soft-skipped rows back into the
    # response so the client can surface "X updated, Y skipped" in one
    # toast. Explicit path's ``skipped_results`` is empty.
    return UpdateAuthApiResponse(
        results=results + skipped_results,
        idempotency_key=idempotency_key,
        auths=auths_hydrated,
    )
