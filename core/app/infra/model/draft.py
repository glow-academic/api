"""Model draft logic — canonical draft + form-state flow."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.model.permissions import compute_can_draft
from app.infra.model.refresh import refresh_model_impl
from app.infra.model.types import (
    DraftFormState,
    PatchModelDraftApiRequest,
    PatchModelDraftApiResponse,
    SaveModelFieldError,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.tools.sanitize import sanitize_model_kwargs
from app.tools.entries.model_drafts.create import create_model_draft
from app.tools.entries.model_drafts.get import get_model_drafts
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.search import search_flags
from app.tools.resources.flags.get import get_flags
from app.tools.resources.modalities.search import search_modalities
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names
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

    if request.active_flag is not None and request.active_flag_id is None:
        async with pool.acquire() as conn:
            matches = await search_flags(conn, redis, search=None, flag_type="model_active", limit_count=20)
        active_match = next((item for item in matches if item.type == "model_active"), None)
        if request.active_flag and active_match and active_match.id:
            request.active_flag_id = active_match.id
        elif request.active_flag:
            errors.append(SaveModelFieldError(field="active_flag", message="Active flag resource not found"))

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

    if request.pricing is not None and request.pricing_ids is None:
        async with pool.acquire() as conn:
            existing = await search_pricing(conn, redis, search=None, limit_count=1000, model=True)
        pricing_map = {item.pricing_type.lower(): item.id for item in existing if item.pricing_type and item.id}
        resolved_ids = []
        for pricing in request.pricing:
            pricing_id = pricing_map.get(pricing.lower())
            if pricing_id:
                resolved_ids.append(pricing_id)
            else:
                errors.append(SaveModelFieldError(field="pricing", message=f'Pricing "{pricing}" not found'))
        if not any(error.field == "pricing" for error in errors):
            request.pricing_ids = resolved_ids

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

    request.flag_ids = _dedupe_ids(
        (request.flag_ids or [])
        + [
            flag_id
            for flag_id in [
                request.active_flag_id,
                request.modalities_enabled_flag_id,
                request.temperature_enabled_flag_id,
                request.pricing_enabled_flag_id,
                request.voices_enabled_flag_id,
                request.reasoning_levels_enabled_flag_id,
                request.qualities_enabled_flag_id,
            ]
            if flag_id
        ]
    )
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

    if not compute_can_draft(role_level=profile.role_level, role_permissions=profile.role_permissions):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create or edit model drafts.",
        )

    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                drafts = await get_model_drafts(conn, [idempotency_key])
                async with conn.transaction():
                    if drafts:
                        draft = drafts[0]
                        await create_model_draft(
                            conn,
                            session_id=session_id,
                            id=idempotency_key,
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
                            session_id=session_id,
                            id=idempotency_key,
                            soft=False,
                            profile_ids=[profile.profiles_id],
                        )
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
            draft_id=idempotency_key,
            idempotency_key=idempotency_key,
            message="Draft accepted" if accept else "Draft rejected",
            form_state=DraftFormState(),
        )

    errors = await _resolve_creatable_values(pool, redis, request)
    if errors:
        raise HTTPException(status_code=400, detail=[error.model_dump() for error in errors])

    if request.flag_ids:
        async with pool.acquire() as conn:
            selected_flags = await get_flags(conn, request.flag_ids, redis, bypass_cache=True)
        for flag in selected_flags:
            key = flag.name.replace("model_", "") if getattr(flag, "name", None) else None
            field_name = MODEL_FLAG_KEY_FIELDS.get(key or "")
            if field_name and getattr(request, field_name, None) is None and flag.id:
                setattr(request, field_name, flag.id)

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_model_draft(
                conn,
                session_id=session_id,
                id=idempotency_key,
                soft=soft,
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

    resolved_name = request.name
    if request.name_id and resolved_name is None:
        async with pool.acquire() as conn:
            matches = await get_names(conn, [request.name_id], redis, bypass_cache=True)
        resolved_name = matches[0].name if matches else None

    resolved_description = request.description
    if request.description_id and resolved_description is None:
        async with pool.acquire() as conn:
            matches = await get_descriptions(conn, [request.description_id], redis, bypass_cache=True)
        resolved_description = matches[0].description if matches else None

    resolved_value = request.value
    if request.value_id and resolved_value is None:
        async with pool.acquire() as conn:
            matches = await get_values(conn, [request.value_id], redis, bypass_cache=True)
        resolved_value = matches[0].value if matches else None

    resolved_provider = request.provider
    if request.provider_id and resolved_provider is None:
        async with pool.acquire() as conn:
            matches = await get_providers(conn, [request.provider_id], redis, bypass_cache=True)
        resolved_provider = matches[0].name if matches else None

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
        active_flag_id=request.active_flag_id,
        modalities_enabled_flag_id=request.modalities_enabled_flag_id,
        temperature_enabled_flag_id=request.temperature_enabled_flag_id,
        pricing_enabled_flag_id=request.pricing_enabled_flag_id,
        voices_enabled_flag_id=request.voices_enabled_flag_id,
        reasoning_levels_enabled_flag_id=request.reasoning_levels_enabled_flag_id,
        qualities_enabled_flag_id=request.qualities_enabled_flag_id,
        department_ids=request.department_ids or [],
        modality_ids=request.modality_ids or [],
        pricing_ids=request.pricing_ids or [],
        quality_ids=request.quality_ids or [],
        reasoning_level_ids=request.reasoning_level_ids or [],
        temperature_level_ids=request.temperature_level_ids or [],
        voice_ids=request.voice_ids or [],
        pending_ids=request.pending_ids or [],
    )

    if not soft:
        await refresh_model_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            targets=["model_drafts_mv"],
            operation_key=result.id,
        )

    return PatchModelDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=result.id,
        message="Draft created (pending acceptance)" if soft else "Draft created successfully",
        form_state=form_state,
    )
