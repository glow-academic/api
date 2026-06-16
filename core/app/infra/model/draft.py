"""Model draft logic — canonical draft + form-state flow."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.drafts.ownership import enforce_draft_owner
from app.infra.model.permissions import compute_can_draft
from app.infra.model.refresh import refresh_model_impl
from app.infra.model.types import (
    DraftFormState,
    PatchModelDraftApiRequest,
    PatchModelDraftApiResponse,
    SaveModelFieldError,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.infra.tools.sanitize import sanitize_model_kwargs
from app.tools.entries.model_drafts.create import create_model_draft
from app.tools.entries.model_drafts.get import get_model_drafts
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.entries.soft_calls.search import search_soft_calls

ARTIFACT = "model"
OPERATION = "draft"


async def _maybe_auto_accept_model_draft(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    draft_id: UUID,
    session_id: UUID,
    profile_ids: list[UUID],
) -> bool:
    """Merge step — auto-accept the draft when no pending fields remain."""
    async with pool.acquire() as conn:
        ledger_entries = await search_soft_calls(
            conn,
            redis,
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
        drafts = await get_model_drafts(conn, [draft_id], redis, active=None)
    if not drafts:
        return False
    draft = drafts[0]
    if (
        getattr(draft, "pending_department_ids", None)
        or getattr(draft, "pending_description_ids", None)
        or getattr(draft, "pending_flag_ids", None)
        or getattr(draft, "pending_modality_ids", None)
        or getattr(draft, "pending_name_ids", None)
        or getattr(draft, "pending_pricing_ids", None)
        or getattr(draft, "pending_provider_ids", None)
        or getattr(draft, "pending_quality_ids", None)
        or getattr(draft, "pending_reasoning_level_ids", None)
        or getattr(draft, "pending_temperature_level_ids", None)
        or getattr(draft, "pending_value_ids", None)
        or getattr(draft, "pending_voice_ids", None)
    ):
        return False

    async with pool.acquire() as conn:
        async with transaction_with_writeback(conn):
            await create_model_draft(
                conn,
                redis, session_id=session_id,
                id=draft_id,
                soft=False,
                name_ids=draft.name_ids,
                description_ids=draft.description_ids,
                flag_ids=draft.flag_ids,
                department_ids=draft.department_ids,
                modality_ids=draft.modality_ids,
                pricing_ids=draft.pricing_ids,
                provider_ids=draft.provider_ids,
                quality_ids=draft.quality_ids,
                reasoning_level_ids=draft.reasoning_level_ids,
                temperature_level_ids=draft.temperature_level_ids,
                voice_ids=draft.voice_ids,
                value_id=draft.value_id,
                profile_ids=draft.profile_ids or profile_ids,
                pending_ids=set(),
            )
            await create_soft_call(
                conn,
                redis,
                call_id=call_id,
                artifact=ARTIFACT,
                operation=OPERATION,
                artifact_id=draft_id,
                status="accepted",
            )
    async with pool.acquire() as conn:
        await refresh_soft_calls(conn)
    return True
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.search import search_flags
from app.tools.resources.modalities.search import search_modalities
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names
from app.tools.resources.pricing.create import create_pricing
from app.tools.resources.pricing.search import search_pricing
from app.tools.resources.providers.get import get_providers
from app.tools.resources.providers.search import search_providers
from app.tools.resources.qualities.search import search_qualities
from app.tools.resources.reasoning_levels.search import search_reasoning_levels
from app.tools.resources.temperature_levels.search import search_temperature_levels
from app.tools.resources.values.create import create_value
from app.tools.resources.values.get import get_values
from app.tools.resources.values.search import search_values
from app.tools.resources.voices.create import create_voice
from app.tools.resources.voices.search import search_voices
from app.utils.cache.hedged_row import transaction_with_writeback


def _dedupe_ids(ids: list[UUID] | None) -> list[UUID]:
    if not ids:
        return []
    seen: set[UUID] = set()
    ordered: list[UUID] = []
    for item in ids:
        if item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


MODEL_FLAG_KEY_FIELDS = {
    "active": "active_flag_id",
    "modalities_enabled": "modalities_enabled_flag_id",
    "temperature_enabled": "temperature_enabled_flag_id",
    "pricing_enabled": "pricing_enabled_flag_id",
    "voices_enabled": "voices_enabled_flag_id",
    "reasoning_levels_enabled": "reasoning_levels_enabled_flag_id",
    "qualities_enabled": "qualities_enabled_flag_id",
}


# Denormalized bool field name → flag type in flags_resource (artifact-prefixed).
MODEL_DENORM_FLAG_FIELDS = {
    "active": "model_active",
    "modalities_enabled": "model_modalities_enabled",
    "temperature_enabled": "model_temperature_enabled",
    "pricing_enabled": "model_pricing_enabled",
    "voices_enabled": "model_voices_enabled",
    "reasoning_levels_enabled": "model_reasoning_levels_enabled",
    "qualities_enabled": "model_qualities_enabled",
}


async def _resolve_creatable_values(
    pool: asyncpg.Pool,
    redis: Redis,
    request: PatchModelDraftApiRequest,
) -> list[SaveModelFieldError]:
    """Resolve raw values to resource IDs, mutating request in place."""

    errors: list[SaveModelFieldError] = []

    if request.name is not None and request.name_id is None:
        async with pool.acquire() as conn:
            existing = await search_names(conn, redis, search=request.name, limit_count=10, model=True)
        match = next((item for item in existing if item.name and item.name.lower() == request.name.lower()), None)
        if match and match.id:
            request.name_id = match.id
        else:
            async with pool.acquire() as conn:
                created = await create_name(conn, request.name, redis)
            request.name_id = created.id

    if request.description is not None and request.description_id is None:
        async with pool.acquire() as conn:
            existing = await search_descriptions(conn, redis, search=request.description, limit_count=10, model=True)
        match = next(
            (
                item
                for item in existing
                if item.description and item.description.lower() == request.description.lower()
            ),
            None,
        )
        if match and match.id:
            request.description_id = match.id
        else:
            async with pool.acquire() as conn:
                created = await create_description(conn, request.description, redis)
            request.description_id = created.id

    if request.value is not None and request.value_id is None:
        async with pool.acquire() as conn:
            existing = await search_values(conn, redis, search=request.value, limit_count=10, model=True)
        match = next((item for item in existing if item.value and item.value.lower() == request.value.lower()), None)
        if match and match.id:
            request.value_id = match.id
        else:
            async with pool.acquire() as conn:
                created = await create_value(conn, request.value, redis, value_type="model")
            request.value_id = created.id

    if request.provider is not None and request.provider_id is None:
        async with pool.acquire() as conn:
            existing = await search_providers(conn, redis, search=request.provider, limit_count=20, model=True)
        match = next(
            (
                item
                for item in existing
                if (item.name and item.name.lower() == request.provider.lower())
                or (getattr(item, "value", None) and getattr(item, "value").lower() == request.provider.lower())
            ),
            None,
        )
        if match and match.id:
            request.provider_id = match.id
        else:
            errors.append(
                SaveModelFieldError(field="provider", message=f'Provider "{request.provider}" not found')
            )

    # Canonical: denorm bool fields → flag_ids via (type, value) lookup.
    denorm_values: dict[str, bool] = {}
    for field_name, flag_type in MODEL_DENORM_FLAG_FIELDS.items():
        v = getattr(request, field_name, None)
        if v is not None:
            denorm_values[flag_type] = bool(v)
    if denorm_values:
        async with pool.acquire() as conn:
            all_rows = await search_flags(
                conn, redis, search=None, limit_count=200, bypass_cache=True
            )
        resolved_ids: list[UUID] = list(request.flag_ids or [])
        seen = set(resolved_ids)
        for ftype, desired in denorm_values.items():
            match = next(
                (
                    f
                    for f in all_rows
                    if (getattr(f, "type", None) == ftype
                        or getattr(f, "name", None) == ftype)
                    and getattr(f, "value", None) is desired
                ),
                None,
            )
            if match and match.id and match.id not in seen:
                resolved_ids.append(match.id)
                seen.add(match.id)
        request.flag_ids = resolved_ids

    if request.departments is not None and request.department_ids is None:
        async with pool.acquire() as conn:
            all_departments = await search_departments(conn, redis, search=None, limit_count=1000)
        dept_name_map = {item.name.lower(): item.id for item in all_departments if item.name and item.id}
        resolved_ids: list[UUID] = []
        for department_name in request.departments:
            department_id = dept_name_map.get(department_name.lower())
            if department_id:
                resolved_ids.append(department_id)
            else:
                errors.append(
                    SaveModelFieldError(field="departments", message=f'Department "{department_name}" not found')
                )
        if not any(error.field == "departments" for error in errors):
            request.department_ids = resolved_ids

    if request.modalities is not None and request.modality_ids is None:
        async with pool.acquire() as conn:
            existing = await search_modalities(conn, redis, search=None, limit_count=1000, model=True)
        modality_map = {item.modality.lower(): item.id for item in existing if item.modality and item.id}
        resolved_ids = []
        for modality in request.modalities:
            modality_id = modality_map.get(modality.lower())
            if modality_id:
                resolved_ids.append(modality_id)
            else:
                errors.append(
                    SaveModelFieldError(field="modalities", message=f'Modality "{modality}" not found')
                )
        if not any(error.field == "modalities" for error in errors):
            request.modality_ids = resolved_ids

    # Inline-created pricing rows: entries without id are created here. The
    # value list is updated in place so the form_state echo carries resolved
    # ids back to the client; ids merge into request.pricing_ids so the
    # downstream draft row sees a single flat list.
    if request.pricing:
        resolved_pricing_ids: list[UUID] = []
        async with pool.acquire() as conn:
            for value in request.pricing:
                if value.id is None:
                    created = await create_pricing(
                        conn,
                        pricing_type=value.pricing_type,
                        price=value.price,
                        unit_name=value.unit_name,
                        unit_category=value.unit_category,
                        unit_value=value.unit_value,
                        redis=redis,
                    )
                    if created.id is None:
                        errors.append(
                            SaveModelFieldError(
                                field="pricing",
                                message=f'Failed to create pricing "{value.pricing_type}"',
                            )
                        )
                        continue
                    value.id = created.id
                resolved_pricing_ids.append(value.id)
        existing_ids = list(request.pricing_ids or [])
        seen = set(existing_ids)
        for pid in resolved_pricing_ids:
            if pid not in seen:
                existing_ids.append(pid)
                seen.add(pid)
        request.pricing_ids = existing_ids

    if request.qualities is not None and request.quality_ids is None:
        async with pool.acquire() as conn:
            existing = await search_qualities(conn, redis, search=None, limit_count=1000, model=True)
        quality_map = {item.quality.lower(): item.id for item in existing if item.quality and item.id}
        resolved_ids = []
        for quality in request.qualities:
            quality_id = quality_map.get(quality.lower())
            if quality_id:
                resolved_ids.append(quality_id)
            else:
                errors.append(SaveModelFieldError(field="qualities", message=f'Quality "{quality}" not found'))
        if not any(error.field == "qualities" for error in errors):
            request.quality_ids = resolved_ids

    if request.reasoning_levels is not None and request.reasoning_level_ids is None:
        async with pool.acquire() as conn:
            existing = await search_reasoning_levels(conn, redis, search=None, limit_count=1000, model=True)
        reasoning_map = {
            item.reasoning_level.lower(): item.id
            for item in existing
            if item.reasoning_level and item.id
        }
        resolved_ids = []
        for reasoning_level in request.reasoning_levels:
            reasoning_level_id = reasoning_map.get(reasoning_level.lower())
            if reasoning_level_id:
                resolved_ids.append(reasoning_level_id)
            else:
                errors.append(
                    SaveModelFieldError(
                        field="reasoning_levels",
                        message=f'Reasoning level "{reasoning_level}" not found',
                    )
                )
        if not any(error.field == "reasoning_levels" for error in errors):
            request.reasoning_level_ids = resolved_ids

    if request.temperature_levels is not None and request.temperature_level_ids is None:
        async with pool.acquire() as conn:
            existing = await search_temperature_levels(conn, redis, search=None, limit_count=1000, model=True)
        temperature_map = {
            str(item.temperature).lower(): item.id
            for item in existing
            if item.temperature is not None and item.id
        }
        resolved_ids = []
        for temperature_level in request.temperature_levels:
            temperature_level_id = temperature_map.get(temperature_level.lower())
            if temperature_level_id:
                resolved_ids.append(temperature_level_id)
            else:
                errors.append(
                    SaveModelFieldError(
                        field="temperature_levels",
                        message=f'Temperature level "{temperature_level}" not found',
                    )
                )
        if not any(error.field == "temperature_levels" for error in errors):
            request.temperature_level_ids = resolved_ids

    if request.voices is not None and request.voice_ids is None:
        async with pool.acquire() as conn:
            existing = await search_voices(conn, redis, search=None, limit_count=1000, model=True)
        voice_map = {item.voice.lower(): item.id for item in existing if item.voice and item.id}
        resolved_ids = []
        missing_voices = []
        for voice in request.voices:
            voice_id = voice_map.get(voice.lower())
            if voice_id:
                resolved_ids.append(voice_id)
            else:
                missing_voices.append(voice)
        if missing_voices:
            async with pool.acquire() as conn:
                for voice in missing_voices:
                    created = await create_voice(conn, voice, redis)
                    if created.id:
                        resolved_ids.append(created.id)
        request.voice_ids = resolved_ids

    request.flag_ids = _dedupe_ids(request.flag_ids)
    request.department_ids = _dedupe_ids(request.department_ids)
    request.modality_ids = _dedupe_ids(request.modality_ids)
    request.pricing_ids = _dedupe_ids(request.pricing_ids)
    request.quality_ids = _dedupe_ids(request.quality_ids)
    request.reasoning_level_ids = _dedupe_ids(request.reasoning_level_ids)
    request.temperature_level_ids = _dedupe_ids(request.temperature_level_ids)
    request.voice_ids = _dedupe_ids(request.voice_ids)

    return errors


async def patch_model_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchModelDraftApiRequest | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **kwargs: Any,
) -> PatchModelDraftApiResponse:
    """Patch model draft using the canonical draft contract."""

    if request is None:
        filtered = sanitize_model_kwargs(
            kwargs,
            list_fields={
                "departments",
                "department_ids",
                "modalities",
                "modality_ids",
                "pricing",
                "pricing_ids",
                "qualities",
                "quality_ids",
                "reasoning_levels",
                "reasoning_level_ids",
                "temperature_levels",
                "temperature_level_ids",
                "voices",
                "voice_ids",
                "flag_ids",
                "pending_ids",
            },
            value_id_pairs=[
                ("name", "name_id"),
                ("description", "description_id"),
                ("value", "value_id"),
                ("provider", "provider_id"),
            ],
        )
        if draft_id:
            filtered["draft_id"] = draft_id
        request = PatchModelDraftApiRequest(**filtered)

    request.draft_id = request.draft_id or request.input_draft_id or draft_id
    request.input_draft_id = request.input_draft_id or request.draft_id
    idempotency_key = idempotency_key or request.idempotency_key
    if accept is None and idempotency_key is not None:
        accept = request.accept

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
        if not compute_can_draft(role_level=profile.role_level, role_permissions=profile.role_permissions):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to create or edit model drafts.",
            )

    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(
                status_code=404,
                detail="No pending model draft for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                await enforce_draft_owner(
                    conn,
                    redis,
                    draft_id=target_id,
                    getter=get_model_drafts,
                    caller_session_id=session_id,
                    caller_profile_id=profile.profiles_id,
                    role_level=profile.role_level,
                    artifact=ARTIFACT,
                )
                drafts = await get_model_drafts(conn, [target_id], redis, active=None)
                async with transaction_with_writeback(conn):
                    if drafts:
                        draft = drafts[0]
                        await create_model_draft(
                            conn,
                            redis, session_id=session_id,
                            id=target_id,
                            soft=False,
                            name_ids=draft.name_ids,
                            description_ids=draft.description_ids,
                            flag_ids=draft.flag_ids,
                            department_ids=draft.department_ids,
                            modality_ids=draft.modality_ids,
                            pricing_ids=draft.pricing_ids,
                            provider_ids=draft.provider_ids,
                            quality_ids=draft.quality_ids,
                            reasoning_level_ids=draft.reasoning_level_ids,
                            temperature_level_ids=draft.temperature_level_ids,
                            voice_ids=draft.voice_ids,
                            value_id=draft.value_id,
                            profile_ids=draft.profile_ids or [profile.profiles_id],
                            pending_ids=set(),
                        )
                    else:
                        await create_model_draft(
                            conn,
                            redis, session_id=session_id,
                            id=target_id,
                            soft=False,
                            profile_ids=[profile.profiles_id],
                        )

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                redis,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation=OPERATION,
                artifact_id=target_id,
                status="accepted" if accept else "rejected",
            )
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

        await refresh_model_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            targets=["model_drafts_mv"],
            operation_key=idempotency_key,
        )
        return PatchModelDraftApiResponse(
            success=True,
            draft_id=target_id,
            idempotency_key=idempotency_key,
            message="Draft accepted" if accept else "Draft rejected",
            form_state=DraftFormState(),
        )

    with timed("resolve_values"):
        errors = await _resolve_creatable_values(pool, redis, request)
    if errors:
        raise HTTPException(status_code=400, detail=[error.model_dump() for error in errors])

    with timed("db_write"):
     async with pool.acquire() as conn:
        await enforce_draft_owner(
            conn,
            redis,
            draft_id=idempotency_key,
            getter=get_model_drafts,
            caller_session_id=session_id,
            caller_profile_id=profile.profiles_id,
            role_level=profile.role_level,
            artifact=ARTIFACT,
        )
        async with transaction_with_writeback(conn):
            result = await create_model_draft(
                conn,
                redis, session_id=session_id,
                id=idempotency_key,
                soft=soft,
                name=request.name or "",
                profile_ids=[profile.profiles_id],
                name_ids=[request.name_id] if request.name_id else None,
                description_ids=[request.description_id] if request.description_id else None,
                flag_ids=request.flag_ids,
                department_ids=request.department_ids,
                modality_ids=request.modality_ids,
                pricing_ids=request.pricing_ids,
                provider_ids=[request.provider_id] if request.provider_id else None,
                quality_ids=request.quality_ids,
                reasoning_level_ids=request.reasoning_level_ids,
                temperature_level_ids=request.temperature_level_ids,
                value_id=request.value_id,
                voice_ids=request.voice_ids,
                pending_ids=set(request.pending_ids) if request.pending_ids else None,
            )

            # Pending ledger row tied to this tool call.
            if soft and idempotency_key is not None:
                await create_soft_call(
                    conn,
                    redis,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation=OPERATION,
                    artifact_id=result.id,
                )

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    resolved_name = request.name
    if request.name_id and resolved_name is None:
        matches = await get_names(pool, [request.name_id], redis, bypass_cache=True)
        resolved_name = matches[0].name if matches else None

    resolved_description = request.description
    if request.description_id and resolved_description is None:
        matches = await get_descriptions(pool, [request.description_id], redis, bypass_cache=True)
        resolved_description = matches[0].description if matches else None

    resolved_value = request.value
    if request.value_id and resolved_value is None:
        matches = await get_values(pool, [request.value_id], redis, bypass_cache=True)
        resolved_value = matches[0].value if matches else None

    resolved_provider = request.provider
    if request.provider_id and resolved_provider is None:
        matches = await get_providers(pool, [request.provider_id], redis, bypass_cache=True)
        resolved_provider = matches[0].name if matches else None

    # Re-derive denorm bools from final flag_ids so client echo matches what
    # the server actually persisted.
    echoed_bools: dict[str, bool | None] = {
        f: getattr(request, f, None) for f in MODEL_DENORM_FLAG_FIELDS
    }
    if request.flag_ids:
        flag_rows = await get_flags(pool, request.flag_ids, redis, bypass_cache=True
        )
        type_to_field = {v: k for k, v in MODEL_DENORM_FLAG_FIELDS.items()}
        for row in flag_rows:
            rtype = getattr(row, "type", None) or getattr(row, "name", None)
            field = type_to_field.get(rtype or "")
            if field:
                echoed_bools[field] = getattr(row, "value", None)

    form_state = DraftFormState(
        name_id=request.name_id,
        name=resolved_name,
        description_id=request.description_id,
        description=resolved_description,
        value_id=request.value_id,
        value=resolved_value,
        provider_id=request.provider_id,
        provider=resolved_provider,
        flag_ids=request.flag_ids or [],
        active=echoed_bools.get("active"),
        modalities_enabled=echoed_bools.get("modalities_enabled"),
        temperature_enabled=echoed_bools.get("temperature_enabled"),
        pricing_enabled=echoed_bools.get("pricing_enabled"),
        voices_enabled=echoed_bools.get("voices_enabled"),
        reasoning_levels_enabled=echoed_bools.get("reasoning_levels_enabled"),
        qualities_enabled=echoed_bools.get("qualities_enabled"),
        department_ids=request.department_ids or [],
        modality_ids=request.modality_ids or [],
        pricing_ids=request.pricing_ids or [],
        pricing=request.pricing or [],
        quality_ids=request.quality_ids or [],
        reasoning_level_ids=request.reasoning_level_ids or [],
        temperature_level_ids=request.temperature_level_ids or [],
        voice_ids=request.voice_ids or [],
        pending_ids=request.pending_ids or [],
    )

    auto_accepted = False
    if not soft:
        with timed("auto_accept"):
            auto_accepted = await _maybe_auto_accept_model_draft(
                pool, redis,
                draft_id=result.id,
                session_id=session_id,
                profile_ids=[profile.profiles_id],
            )
        with timed("refresh"):
            await refresh_model_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                targets=["model_drafts_mv"],
                operation_key=result.id,
            )

    if auto_accepted:
        message = "Draft accepted (all fields resolved)"
    elif soft:
        message = "Draft created (pending acceptance)"
    else:
        message = "Draft created successfully"

    return PatchModelDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=result.id,
        message=message,
        form_state=form_state,
    )
