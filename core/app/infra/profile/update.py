"""Profile update logic — composable infra architecture."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile.permissions_context import (
    create_denormalized_snapshot,
    resolve_profile_permissions_context,
    resolve_profile_values,
)
from app.infra.profile.primary_department import (
    resolve_primary_departments_id,
)
from app.infra.profile.refresh import refresh_profile_impl
from app.infra.profile.types import (
    ListProfilesApiProfile,
    UpdateProfileApiRequest,
    UpdateProfileApiResponse,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.profile.get import (
    get_profiles as get_profile_artifacts,
)
from app.tools.artifacts.profile.update import _UNSET
from app.tools.artifacts.profile.update import (
    update_profile as update_profile_artifact,
)
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls

ARTIFACT = "profile"


async def update_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdateProfileApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdateProfileApiResponse:
    """Profile bulk update using composable infra functions.

    Three call shapes:
      - First call (explicit): ``request.profiles`` required — per-row patches.
      - First call (all-matching): ``request.all=true`` plus ``patch``
        plus filter fields. The impl resolves matching ids, clones
        the patch per id (stamping each id), then runs the existing
        per-row update flow. Per-row permission failures soft-skip.
      - Ack call: ``idempotency_key`` + ``accept`` only.
    """
    from app.infra.profile.permissions import compute_can_edit
    from app.infra.profile.types import ProfileResultItem

    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key is not None and accept is None:
        accept = request.accept

    # ── Short-circuit: ack path ───────────────────────────────────────
    # Hoisted above the per-row permission loop because under ack and
    # all-matching paths ``request.profiles`` is None on entry; running
    # the loop first would either raise or silently no-op. Persona's
    # canonical pattern.
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "update":
            raise HTTPException(
                status_code=404,
                detail="No pending profile update for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await update_profile_artifact(
                        conn,
                        target_id,
                        soft=False,
                        redis=redis,
                    )

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation="update",
                artifact_id=target_id,
                status="accepted" if accept else "rejected",
            )
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

        await refresh_profile_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            operation_key=idempotency_key,
        )

        return UpdateProfileApiResponse(
            results=[
                ProfileResultItem(
                    success=True,
                    profile_id=target_id,
                    message="Update accepted" if accept else "Update rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── All-matching path: resolve ids + synthesize per-row items ─────
    # Past the ack short-circuit and ``all=true`` ⇒ enumerate every
    # profile matching the filter, then clone ``request.patch`` per
    # id (stamping the resolved id). The downstream per-row flow runs
    # unchanged. Per-row permission failures soft-skip (collected into
    # ``skipped_results`` and threaded into the final response).
    skipped_results: list[ProfileResultItem] = []

    if request.all:
        if request.patch is None:
            raise HTTPException(
                status_code=400,
                detail="`patch` is required when `all=true` "
                "(it carries the shared change set applied to every matched row).",
            )
        from app.infra.profile.resolve_matching_ids import resolve_matching_profile_ids
        from app.infra.profile.types import UpdateProfileItem

        matching = await resolve_matching_profile_ids(
            pool, redis,
            profile_id=profile_id,
            search=request.search,
            cohort_ids=request.cohort_ids,
            filter_department_ids=request.filter_department_ids,
            role_filter=request.role_filter,
            cohort_search=request.cohort_search,
            department_search=request.department_search,
            role_search=request.role_search,
            flag_search=request.flag_search,
        )
        excluded = set(request.excluded_ids or [])
        resolved_ids = [pid for pid in matching if pid not in excluded]

        if not resolved_ids:
            # Empty matching set — well-formed intent, just no rows.
            return UpdateProfileApiResponse(results=[], idempotency_key=idempotency_key)

        # Clone the patch per matched row, stamping the resolved id.
        # ``model_dump(exclude_unset=True, exclude={"profile_id"})`` keeps
        # sparse semantics — only fields the client actually set are written.
        patch_fields = request.patch.model_dump(
            exclude_unset=True, exclude={"profile_id"},
        )
        synth_items = [
            UpdateProfileItem(profile_id=pid, **patch_fields) for pid in resolved_ids
        ]
        # Splice into the request shape downstream code expects.
        request = request.model_copy(update={"profiles": synth_items})

    # ── First-call requirements ───────────────────────────────────────
    if not request.profiles:
        raise HTTPException(
            status_code=400,
            detail="`request.profiles` is required for first-call update "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with `patch` and filter fields).",
        )

    items = request.profiles

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
            target_is_self = item.profile_id == profile_id
            perms = await resolve_profile_permissions_context(conn, item.profile_id)
            if not perms.exists:
                if is_all_matching:
                    skipped_results.append(ProfileResultItem(
                        success=False, profile_id=item.profile_id,
                        message=f"Profile {item.profile_id} not found (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Profile {item.profile_id} not found.",
                )
            if not compute_can_edit(
                role_level=profile.role_level,
                role_permissions=profile.role_permissions,
                target_is_self=target_is_self,
                target_department_ids=perms.department_ids,
                user_department_ids=profile.department_ids,
            ):
                if is_all_matching:
                    skipped_results.append(ProfileResultItem(
                        success=False, profile_id=item.profile_id,
                        message=f"No permission to update profile {item.profile_id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this profile.",
                )

            permitted_items.append(item)

    if is_all_matching:
        items = permitted_items
        if not items:
            return UpdateProfileApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
            )

    has_errors = False
    error_results: list[ProfileResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_profile_values(
                conn,
                redis,
                item,
                is_create=False,
            )
            if item_errors:
                has_errors = True
                error_results.append(
                    ProfileResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(ProfileResultItem(success=True, message="Validated"))

    if has_errors:
        return UpdateProfileApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    results: list[ProfileResultItem] = []

    for item in items:
        async with pool.acquire() as conn:
            existing = await get_profile_artifacts(
                conn,
                [item.profile_id],
                names=True,
                departments=True,
                roles=True,
                emails=True,
            )

        if existing:
            artifact = existing[0]
            eff_name_id = item.name_id or (artifact.name_ids[0] if artifact.name_ids else None)
            eff_department_ids = (
                item.department_ids
                if item.department_ids is not None
                else list(artifact.department_ids or [])
            )
            eff_role_id = (
                item.role_id
                if item.role_id is not None
                else (artifact.role_ids[0] if artifact.role_ids else None)
            )
            eff_email_ids = (
                item.email_ids
                if item.email_ids is not None
                else list(artifact.email_ids or [])
            )
        else:
            eff_name_id = item.name_id
            eff_department_ids = item.department_ids
            eff_role_id = item.role_id
            eff_email_ids = item.email_ids

        profiles_resource_id = None
        if not soft:
            async with pool.acquire() as conn:
                profiles_resource_id = await create_denormalized_snapshot(
                    conn,
                    redis,
                    name_id=eff_name_id,
                    department_ids=eff_department_ids,
                    email_ids=eff_email_ids,
                    role_id=eff_role_id,
                )

        async with pool.acquire() as conn:
            async with conn.transaction():
                primary_departments_id: object = _UNSET
                if item.primary_department_id is not None:
                    primary_departments_id = await resolve_primary_departments_id(
                        conn,
                        redis,
                        departments_id=item.primary_department_id,
                        soft=soft,
                    )

                await update_profile_artifact(
                    conn,
                    item.profile_id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    primary_departments_id=primary_departments_id,
                    department_ids=item.department_ids,
                    flag_ids=item.flag_ids or None,
                    email_ids=item.email_ids,
                    role_ids=[item.role_id] if item.role_id else None,
                    profile_ids=[profiles_resource_id] if profiles_resource_id else None,
                    redis=redis,
                    soft=soft,
                )

                if soft and idempotency_key is not None:
                    await create_soft_call(
                        conn,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="update",
                        artifact_id=item.profile_id,
                    )

        results.append(
            ProfileResultItem(
                success=True,
                profile_id=item.profile_id,
                message="Profile updated (pending acceptance)" if soft else "Profile updated successfully",
            )
        )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    if not soft:
        await refresh_profile_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            soft=soft,
            operation_key=idempotency_key or (results[0].profile_id if results else None),
        )

    # ── Hydrate full row content for the client ──────────────────────
    # See ``hydrate_profile_list_rows``: returns the same shape
    # ``/profile/search`` does. Audit framework spreads response fields
    # into ``profile.update.completed``, so the client's ghost rail
    # materializes the changed row directly — no SSR refresh round-trip.
    # Soft-pending updates skip hydration (the dormant patch isn't fully
    # active until ack-accept).
    profiles_rows: list[ListProfilesApiProfile] | None = None
    if not soft:
        from app.infra.profile.hydrate_list_rows import hydrate_profile_list_rows
        updated_ids = [
            r.profile_id for r in results
            if r.success and r.profile_id is not None
        ]
        if updated_ids:
            profiles_rows = await hydrate_profile_list_rows(
                pool, redis, profile_id=profile_id, profile_ids=updated_ids,
            )

    # All-matching path threads soft-skipped rows back into the
    # response so the client can surface "X updated, Y skipped" in
    # one toast. Explicit path's ``skipped_results`` is empty.
    return UpdateProfileApiResponse(
        results=results + skipped_results,
        profiles=profiles_rows,
        idempotency_key=idempotency_key,
    )
