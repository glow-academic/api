"""Setting draft logic — canonical draft-first flow."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.setting.permissions import compute_can_draft
from app.infra.setting.refresh import refresh_setting_impl
from app.infra.setting.types import (
    DraftFormState,
    PatchSettingDraftApiRequest,
    PatchSettingDraftApiResponse,
    SaveSettingFieldError,
)
from app.tools.entries.setting_drafts.create import create_setting_draft
from app.tools.entries.setting_drafts.get import get_setting_drafts
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.entries.soft_calls.search import search_soft_calls
from app.tools.resources.auth_item_keys.create import create_auth_item_key
from app.tools.resources.auth_item_values.create import create_auth_item_value
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.search import search_flags
from app.tools.resources.keys.create import create_key
from app.tools.resources.logins.create import create_logins
from app.tools.resources.logins.search import search_logins
from app.tools.resources.mcp.create import create_mcp
from app.tools.resources.mcp.search import search_mcp
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names
from app.tools.resources.provider_keys.create import create_provider_key
from app.tools.resources.provider_keys.search import search_provider_keys
from app.tools.resources.systems.create import create_system
from app.tools.resources.thresholds.create import create_threshold
from app.tools.resources.thresholds.get import get_thresholds
from app.tools.resources.thresholds.search import search_thresholds
from app.utils.auth.encrypt_api_key import encrypt_api_key

ARTIFACT = "setting"
OPERATION = "draft"


async def _maybe_auto_accept_setting_draft(
    pool: asyncpg.Pool,
    *,
    draft_id: UUID,
    session_id: UUID,
    profile_ids: list[UUID],
) -> bool:
    """Auto-accept the setting draft when no pending fields remain. Mirrors persona/draft.py."""
    async with pool.acquire() as conn:
        ledger_entries = await search_soft_calls(
            conn,
            artifact=ARTIFACT,
            operation=OPERATION,
            artifact_ids=[draft_id],
            status="pending",
            limit=1,
        )
    if not ledger_entries:
        return False
    call_id = ledger_entries[0].call_id

    async with pool.acquire() as conn:
        drafts = await get_setting_drafts(conn, [draft_id], active=None)
    if not drafts:
        return False
    draft = drafts[0]
    pending_lists = [
        getattr(draft, "pending_name_ids", None),
        getattr(draft, "pending_description_ids", None),
        getattr(draft, "pending_department_ids", None),
        getattr(draft, "pending_color_ids", None),
        getattr(draft, "pending_flag_ids", None),
        getattr(draft, "pending_provider_ids", None),
        getattr(draft, "pending_provider_key_ids", None),
        getattr(draft, "pending_auth_ids", None),
        getattr(draft, "pending_auth_item_key_ids", None),
        getattr(draft, "pending_item_ids", None),
        getattr(draft, "pending_threshold_ids", None),
        getattr(draft, "pending_agent_ids", None),
        getattr(draft, "pending_mcp_ids", None),
        getattr(draft, "pending_logins_ids", None),
    ]
    if any(pl for pl in pending_lists if pl):
        return False

    async with pool.acquire() as conn:
        async with conn.transaction():
            await create_setting_draft(
                conn,
                session_id=session_id,
                id=draft_id,
                soft=False,
                agent_ids=draft.agent_ids,
                auth_ids=draft.auth_ids,
                auth_item_key_ids=draft.auth_item_key_ids,
                color_ids=draft.color_ids,
                department_ids=draft.department_ids,
                description_ids=draft.description_ids,
                flag_ids=draft.flag_ids,
                item_ids=draft.item_ids,
                name_ids=draft.name_ids,
                provider_ids=draft.provider_ids,
                provider_key_ids=draft.provider_key_ids,
                threshold_ids=draft.threshold_ids,
                mcp_ids=draft.mcp_ids,
                logins_ids=draft.logins_ids,
                pending_ids=set(),
            )
            await create_soft_call(
                conn,
                call_id=call_id,
                artifact=ARTIFACT,
                operation=OPERATION,
                artifact_id=draft_id,
                status="accepted",
            )
    async with pool.acquire() as conn:
        await refresh_soft_calls(conn)
    return True


async def _resolve_creatable_values(
    pool: asyncpg.Pool,
    redis: Redis,
    request: PatchSettingDraftApiRequest,
) -> list[SaveSettingFieldError]:
    """Resolve raw values to IDs, mutating request in place."""

    errors: list[SaveSettingFieldError] = []

    async with pool.acquire() as conn:
        if request.name is not None and request.name_id is None:
            existing = await search_names(
                conn,
                redis,
                search=request.name,
                limit_count=10,
                setting=True,
            )
            match = next(
                (
                    item
                    for item in existing
                    if item.name and item.name.lower() == request.name.lower()
                ),
                None,
            )
            if match and match.id:
                request.name_id = match.id
            else:
                created = await create_name(conn, request.name, redis)
                request.name_id = created.id

        if request.description is not None and request.description_id is None:
            existing = await search_descriptions(
                conn,
                redis,
                search=request.description,
                limit_count=10,
                setting=True,
            )
            match = next(
                (
                    item
                    for item in existing
                    if item.description
                    and item.description.lower() == request.description.lower()
                ),
                None,
            )
            if match and match.id:
                request.description_id = match.id
            else:
                created = await create_description(conn, request.description, redis)
                request.description_id = created.id

    # Resolve denormalized flag booleans to canonical flag_ids via (type, value)
    # lookup in flags_resource. Explicit flag_ids are retained verbatim; the
    # derived id is merged in so both forms coexist without conflict.
    denorm_flag_values: dict[str, bool] = {}
    if request.active is not None:
        denorm_flag_values["setting_active"] = bool(request.active)
    if request.mcp is not None:
        denorm_flag_values["mcp"] = bool(request.mcp)
    if denorm_flag_values:
        async with pool.acquire() as conn:
            all_flags = await search_flags(
                conn,
                redis,
                search=None,
                limit_count=200,
                bypass_cache=True,
            )
        resolved_flag_ids: list[UUID] = list(request.flag_ids or [])
        resolved_seen = set(resolved_flag_ids)
        for flag_type, desired_value in denorm_flag_values.items():
            match = next(
                (
                    f
                    for f in all_flags
                    if (getattr(f, "type", None) == flag_type
                        or getattr(f, "name", None) == flag_type)
                    and getattr(f, "value", None) is desired_value
                ),
                None,
            )
            if match and match.id and match.id not in resolved_seen:
                resolved_flag_ids.append(match.id)
                resolved_seen.add(match.id)
            elif not match:
                errors.append(
                    SaveSettingFieldError(
                        field=flag_type,
                        message=(
                            f"Flag row not found for type={flag_type} "
                            f"value={desired_value}"
                        ),
                    )
                )
        request.flag_ids = resolved_flag_ids

    if request.departments is not None and request.department_ids is None:
        async with pool.acquire() as conn:
            all_departments = await search_departments(
                conn,
                redis,
                search=None,
                limit_count=1000,
            )
        department_name_map = {
            item.name.lower(): item.id
            for item in all_departments
            if item.name and item.id
        }
        resolved_ids: list[UUID] = []
        for department_name in request.departments:
            department_id = department_name_map.get(department_name.lower())
            if department_id:
                resolved_ids.append(department_id)
            else:
                errors.append(
                    SaveSettingFieldError(
                        field="departments",
                        message=f'Department "{department_name}" not found',
                    )
                )
        if not any(error.field == "departments" for error in errors):
            request.department_ids = resolved_ids

    # Provider keys value-array: two flows.
    #   • key_value present → encrypt, create a fresh keys_resource row, then
    #     create a provider_keys_resource row linking (provider_id, new key_id).
    #   • key_id present → look up existing junction by (provider_id, key_id);
    #     create one if none exists.
    if request.provider_keys:
        resolved_ids: list[UUID] = []
        async with pool.acquire() as conn:
            for value in request.provider_keys:
                if value.id is None:
                    if value.key_value:
                        encrypted = encrypt_api_key(value.key_value)
                        new_key = await create_key(
                            conn,
                            redis,
                            name=value.key_name or "API Key",
                            key=encrypted,
                        )
                        created = await create_provider_key(
                            conn,
                            provider_id=value.provider_id,
                            key_id=new_key.id,
                            redis=redis,
                        )
                        value.id = created.id
                        value.key_id = new_key.id
                        # Don't echo the plaintext back to the client.
                        value.key_value = None
                    elif value.key_id is not None:
                        matches = await search_provider_keys(
                            conn,
                            redis,
                            limit_count=1,
                            provider_ids=[value.provider_id],
                            key_ids=[value.key_id],
                            bypass_cache=True,
                        )
                        if matches and matches[0].id:
                            value.id = matches[0].id
                        else:
                            created = await create_provider_key(
                                conn,
                                provider_id=value.provider_id,
                                key_id=value.key_id,
                                redis=redis,
                            )
                            value.id = created.id
                if value.id:
                    resolved_ids.append(value.id)
        request.provider_key_ids = _merge_unique(request.provider_key_ids, resolved_ids)

    # Auth item keys value-array: same two flows as provider_keys, scoped to
    # (auth_id, item_id, key_id) instead of (provider_id, key_id).
    if request.auth_item_keys:
        resolved_ids = []
        async with pool.acquire() as conn:
            for value in request.auth_item_keys:
                if value.id is None:
                    if value.key_value:
                        encrypted = encrypt_api_key(value.key_value)
                        new_key = await create_key(
                            conn,
                            redis,
                            name=value.key_name or "Auth Secret",
                            key=encrypted,
                        )
                        created = await create_auth_item_key(
                            conn,
                            auth_id=value.auth_id,
                            item_id=value.item_id,
                            key_id=new_key.id,
                            redis=redis,
                        )
                        value.id = created.id
                        value.key_id = new_key.id
                        value.key_value = None
                    elif value.key_id is not None:
                        created = await create_auth_item_key(
                            conn,
                            auth_id=value.auth_id,
                            item_id=value.item_id,
                            key_id=value.key_id,
                            redis=redis,
                        )
                        value.id = created.id
                if value.id:
                    resolved_ids.append(value.id)
        request.auth_item_key_ids = _merge_unique(request.auth_item_key_ids, resolved_ids)

    # Auth item values value-array: (auth_id, item_id, value) — upsert via ON CONFLICT.
    if request.auth_item_values:
        resolved_ids = []
        async with pool.acquire() as conn:
            for value in request.auth_item_values:
                if value.id is None:
                    created = await create_auth_item_value(
                        conn,
                        auth_id=value.auth_id,
                        item_id=value.item_id,
                        value=value.value,
                        redis=redis,
                    )
                    value.id = created.id
                if value.id:
                    resolved_ids.append(value.id)
        request.auth_item_value_ids = _merge_unique(request.auth_item_value_ids, resolved_ids)

    # Logins value-array: resolve id=null entries by searching for an existing
    # row matching (login_type, auth_id) or (login_type, profile_id); create
    # one if none exists. Merges resolved ids into logins_ids.
    if request.logins:
        resolved_ids = []
        async with pool.acquire() as conn:
            for value in request.logins:
                if value.id is None:
                    matches: list = []
                    if value.login_type == "auth" and value.auth_id is not None:
                        matches = await search_logins(
                            conn,
                            redis,
                            limit_count=1,
                            auth_ids=[value.auth_id],
                            login_type="auth",
                            bypass_cache=True,
                        )
                    elif value.login_type == "profile" and value.profile_id is not None:
                        matches = await search_logins(
                            conn,
                            redis,
                            limit_count=1,
                            profile_ids=[value.profile_id],
                            login_type="profile",
                            bypass_cache=True,
                        )
                    if matches and matches[0].id:
                        value.id = matches[0].id
                    else:
                        created = await create_logins(
                            conn,
                            profile_id=value.profile_id,
                            auth_id=value.auth_id,
                            icon_id=value.icon_id,
                            display_name=value.display_name or "",
                            login_type=value.login_type,
                            redis=redis,
                        )
                        value.id = created.id
                if value.id:
                    resolved_ids.append(value.id)
        request.logins_ids = _merge_unique(request.logins_ids, resolved_ids)

    # MCP value-array: single-select via agent_id; reuse existing row for the agent if present.
    if request.mcp_values:
        resolved_mcp_id: UUID | None = None
        async with pool.acquire() as conn:
            value = request.mcp_values[0]
            if value.id is None:
                matches = await search_mcp(
                    conn,
                    redis,
                    limit_count=100,
                    bypass_cache=True,
                )
                match = next(
                    (m for m in matches if getattr(m, "agent_id", None) == value.agent_id),
                    None,
                )
                if match and match.id:
                    value.id = match.id
                else:
                    created = await create_mcp(
                        conn,
                        agent_id=value.agent_id,
                        name=value.name or "",
                        description=value.description or "",
                        redis=redis,
                    )
                    value.id = created.id
            resolved_mcp_id = value.id
        if resolved_mcp_id:
            request.mcp_id = request.mcp_id or resolved_mcp_id

    # Systems value-array: each draft with id=null creates a new
    # systems_resource row; ids are merged into request.system_ids so
    # the junction save picks them up alongside existing selections.
    if request.system_values:
        resolved_ids: list[UUID] = []
        async with pool.acquire() as conn:
            for value in request.system_values:
                if value.id is None:
                    created = await create_system(
                        conn,
                        name=value.name,
                        description=value.description or "",
                        redis=redis,
                        agent_ids=value.agent_ids or None,
                    )
                    value.id = created.id
                if value.id:
                    resolved_ids.append(value.id)
        request.system_ids = _merge_unique(request.system_ids, resolved_ids)

    # Per-type threshold sliders: each value entry carries a (type, value)
    # pair. Find an existing thresholds_resource row with the same
    # (type, value) to reuse, or create a new one. Replace any prior
    # threshold_id of the same type in request.threshold_ids so each
    # type keeps exactly one assignment on the setting.
    if request.threshold_values:
        # Resolve the current thresholds attached to this setting so we can
        # know which ids to strip (when a slider picks a new value for
        # that same type).
        async with pool.acquire() as conn:
            existing_rows = (
                await get_thresholds(
                    conn, list(request.threshold_ids or []), redis, bypass_cache=True
                )
                if request.threshold_ids
                else []
            )
        existing_type_by_id: dict[UUID, str] = {
            row.id: getattr(row, "type", None)
            for row in existing_rows
            if row.id and getattr(row, "type", None)
        }

        resolved_ids: list[UUID] = []
        touched_types: set[str] = set()
        async with pool.acquire() as conn:
            for draft in request.threshold_values:
                touched_types.add(draft.type)
                # Try to reuse an existing row with the exact (type, value).
                # search_thresholds doesn't filter by type/value server-side,
                # so pull a reasonable page and match in Python.
                candidates = await search_thresholds(
                    conn,
                    redis,
                    search=None,
                    limit_count=500,
                    bypass_cache=True,
                )
                match = next(
                    (
                        row
                        for row in candidates
                        if getattr(row, "type", None) == draft.type
                        and getattr(row, "value", None) == draft.value
                    ),
                    None,
                )
                if match and match.id:
                    draft.id = match.id
                else:
                    created = await create_threshold(
                        conn,
                        value=draft.value,
                        redis=redis,
                        threshold_type=draft.type,
                    )
                    draft.id = created.id
                if draft.id:
                    resolved_ids.append(draft.id)

        # Strip prior ids for touched types, then merge resolved ids in.
        kept = [
            tid
            for tid in (request.threshold_ids or [])
            if existing_type_by_id.get(tid) not in touched_types
        ]
        request.threshold_ids = _merge_unique(kept, resolved_ids)

    return errors


def _merge_unique(existing: list[UUID] | None, new_ids: list[UUID]) -> list[UUID]:
    merged = list(existing or [])
    seen = set(merged)
    for item_id in new_ids:
        if item_id not in seen:
            seen.add(item_id)
            merged.append(item_id)
    return merged


async def patch_setting_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchSettingDraftApiRequest,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> PatchSettingDraftApiResponse:
    """Persist canonical setting draft state and return server-authored form state."""

    resolved_draft_id = request.draft_id or request.input_draft_id
    idempotency_key = idempotency_key or request.idempotency_key or resolved_draft_id
    if accept is None and request.idempotency_key is not None:
        accept = request.accept

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

    if not compute_can_draft(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create or edit setting drafts.",
        )

    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(
                status_code=404,
                detail="No pending setting draft for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                drafts = await get_setting_drafts(conn, [target_id], active=None)
                if drafts:
                    draft = drafts[0]
                    async with conn.transaction():
                        await create_setting_draft(
                            conn,
                            session_id=session_id,
                            id=target_id,
                            soft=False,
                            agent_ids=draft.agent_ids,
                            auth_ids=draft.auth_ids,
                            auth_item_key_ids=draft.auth_item_key_ids,
                            color_ids=draft.color_ids,
                            department_ids=draft.department_ids,
                            description_ids=draft.description_ids,
                            flag_ids=draft.flag_ids,
                            item_ids=draft.item_ids,
                            name_ids=draft.name_ids,
                            provider_ids=draft.provider_ids,
                            provider_key_ids=draft.provider_key_ids,
                            threshold_ids=draft.threshold_ids,
                            mcp_ids=draft.mcp_ids,
                            logins_ids=draft.logins_ids,
                            pending_ids=set(),
                        )

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation=OPERATION,
                artifact_id=target_id,
                status="accepted" if accept else "rejected",
            )
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

        if accept:
            await refresh_setting_impl(
                pool,
                redis,
                profile_id=profile_id,
            )

        return PatchSettingDraftApiResponse(
            success=True,
            draft_id=target_id,
            idempotency_key=idempotency_key,
            message="Draft accepted" if accept else "Draft rejected",
            form_state=DraftFormState(),
        )

    errors = await _resolve_creatable_values(pool, redis, request)
    if errors:
        raise HTTPException(
            status_code=400,
            detail=[error.model_dump() for error in errors],
        )

    pending_ids = set(request.pending_ids or [])
    target_draft_id = resolved_draft_id or idempotency_key

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_setting_draft(
                conn,
                session_id=session_id,
                id=target_draft_id,
                soft=soft,
                name=request.name or "",
                agent_ids=request.system_ids,
                auth_ids=request.auth_ids,
                auth_item_key_ids=request.auth_item_key_ids,
                color_ids=request.color_ids,
                department_ids=request.department_ids,
                description_ids=[request.description_id] if request.description_id else None,
                flag_ids=request.flag_ids or None,
                name_ids=[request.name_id] if request.name_id else None,
                provider_ids=request.provider_ids,
                provider_key_ids=request.provider_key_ids,
                threshold_ids=request.threshold_ids,
                mcp_ids=[request.mcp_id] if request.mcp_id else None,
                logins_ids=request.logins_ids,
                pending_ids=pending_ids,
            )

            if soft and idempotency_key is not None:
                await create_soft_call(
                    conn,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation=OPERATION,
                    artifact_id=result.id,
                )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    if not soft:
        await _maybe_auto_accept_setting_draft(
            pool,
            draft_id=result.id,
            session_id=session_id,
            profile_ids=[profile.profiles_id],
        )

    resolved_name = request.name
    if request.name_id and resolved_name is None:
        names = await get_names(pool, [request.name_id], redis)
        resolved_name = names[0].name if names else None

    resolved_description = request.description
    if request.description_id and resolved_description is None:
        descriptions = await get_descriptions(pool, [request.description_id], redis)
        resolved_description = descriptions[0].description if descriptions else None

    # Re-derive denormalized flag booleans from the final flag_ids so the client
    # echo matches whatever the server actually persisted.
    echoed_active: bool | None = request.active
    echoed_mcp: bool | None = request.mcp
    if request.flag_ids:
        async with pool.acquire() as conn:
            flag_rows = await search_flags(
                conn,
                redis,
                search=None,
                limit_count=200,
                bypass_cache=True,
            )
        rows_by_id = {row.id: row for row in flag_rows if getattr(row, "id", None)}
        for fid in request.flag_ids:
            row = rows_by_id.get(fid)
            if not row:
                continue
            rtype = getattr(row, "type", None) or getattr(row, "name", None)
            rval = getattr(row, "value", None)
            if rtype == "setting_active":
                echoed_active = rval
            elif rtype == "mcp":
                echoed_mcp = rval

    form_state = DraftFormState(
        name_id=request.name_id,
        name=resolved_name,
        description_id=request.description_id,
        description=resolved_description,
        flag_ids=request.flag_ids or [],
        active=echoed_active,
        mcp=echoed_mcp,
        department_ids=request.department_ids or [],
        color_ids=request.color_ids or [],
        logins_ids=request.logins_ids or [],
        system_ids=request.system_ids or [],
        mcp_id=request.mcp_id,
        threshold_ids=request.threshold_ids or [],
        provider_key_ids=request.provider_key_ids or [],
        auth_item_key_ids=request.auth_item_key_ids or [],
        auth_item_value_ids=request.auth_item_value_ids or [],
        auth_ids=request.auth_ids or [],
        provider_ids=request.provider_ids or [],
        provider_keys=request.provider_keys or [],
        auth_item_keys=request.auth_item_keys or [],
        auth_item_values=request.auth_item_values or [],
        mcp_values=request.mcp_values or [],
        system_values=request.system_values or [],
        threshold_values=request.threshold_values or [],
        logins=request.logins or [],
        pending_ids=sorted(pending_ids),
    )

    if not soft:
        await refresh_setting_impl(
            pool,
            redis,
            profile_id=profile_id,
        )

    return PatchSettingDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=idempotency_key or result.id,
        message="Draft saved successfully",
        form_state=form_state,
    )
