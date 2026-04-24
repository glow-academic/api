"""Agent draft logic — canonical draft + form-state flow."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.agent.permissions import compute_can_draft
from app.infra.agent.permissions_context import create_denormalized_snapshot
from app.infra.agent.refresh import refresh_agent_impl
from app.infra.agent.types import (
    DraftFormState,
    PatchAgentDraftApiRequest,
    PatchAgentDraftApiResponse,
    SaveAgentFieldError,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.tools.sanitize import sanitize_model_kwargs
from app.tools.entries.agent_drafts.create import create_agent_draft
from app.tools.entries.agent_drafts.get import get_agent_drafts
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.prompts.create import create_prompt
from app.tools.resources.names.search import search_names
from app.tools.resources.qualities.search import search_qualities
from app.tools.resources.reasoning_levels.search import search_reasoning_levels
from app.tools.resources.temperature_levels.search import search_temperature_levels
from app.tools.resources.voices.create import create_voice
from app.tools.resources.voices.search import search_voices


def _dedupe_ids(ids: list[UUID] | None) -> list[UUID]:
    if not ids:
        return []
    ordered: list[UUID] = []
    seen: set[UUID] = set()
    for item in ids:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


async def _resolve_creatable_values(
    pool: asyncpg.Pool,
    redis: Redis,
    request: PatchAgentDraftApiRequest,
) -> list[SaveAgentFieldError]:
    """Resolve raw values to resource IDs, mutating request in place."""

    errors: list[SaveAgentFieldError] = []

    if request.name is not None and request.name_id is None:
        async with pool.acquire() as conn:
            existing = await search_names(conn, redis, search=request.name, limit_count=10, agent=True)
        match = next((item for item in existing if item.name and item.name.lower() == request.name.lower()), None)
        if match and match.id:
            request.name_id = match.id
        else:
            async with pool.acquire() as conn:
                created = await create_name(conn, request.name, redis)
            request.name_id = created.id

    if request.description is not None and request.description_id is None:
        async with pool.acquire() as conn:
            existing = await search_descriptions(conn, redis, search=request.description, limit_count=10, agent=True)
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

    # Resolve denormalized flag booleans to canonical flag_ids via (type, value)
    # lookup in flags_resource.
    denorm_flag_values: dict[str, bool] = {}
    if request.active is not None:
        denorm_flag_values["agent_active"] = bool(request.active)
    if denorm_flag_values:
        async with pool.acquire() as conn:
            all_flags = await search_flags(conn, redis, search=None, limit_count=200, agent=True)
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
                    SaveAgentFieldError(
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
            existing = await search_departments(conn, redis, search=None, limit_count=1000)
        dept_map = {item.name.lower(): item.id for item in existing if item.name and item.id}
        resolved_ids: list[UUID] = []
        for department_name in request.departments:
            department_id = dept_map.get(department_name.lower())
            if department_id:
                resolved_ids.append(department_id)
            else:
                errors.append(
                    SaveAgentFieldError(field="departments", message=f'Department "{department_name}" not found')
                )
        if not any(error.field == "departments" for error in errors):
            request.department_ids = resolved_ids

    if request.reasoning_level is not None and request.reasoning_level_id is None:
        async with pool.acquire() as conn:
            existing = await search_reasoning_levels(conn, redis, search=None, limit_count=1000)
        reasoning_map = {
            item.reasoning_level.lower(): item.id
            for item in existing
            if item.reasoning_level and item.id
        }
        resolved = reasoning_map.get(request.reasoning_level.lower())
        if resolved:
            request.reasoning_level_id = resolved
        else:
            errors.append(
                SaveAgentFieldError(
                    field="reasoning_level",
                    message=f'Reasoning level "{request.reasoning_level}" not found',
                )
            )

    if request.temperature_level is not None and request.temperature_level_id is None:
        async with pool.acquire() as conn:
            existing = await search_temperature_levels(conn, redis, search=None, limit_count=1000)
        temperature_map = {
            str(item.temperature).lower(): item.id
            for item in existing
            if item.temperature is not None and item.id
        }
        resolved = temperature_map.get(request.temperature_level.lower())
        if resolved:
            request.temperature_level_id = resolved
        else:
            errors.append(
                SaveAgentFieldError(
                    field="temperature_level",
                    message=f'Temperature level "{request.temperature_level}" not found',
                )
            )

    if request.voices is not None and request.voice_ids is None:
        async with pool.acquire() as conn:
            existing = await search_voices(conn, redis, search=None, limit_count=1000, agent=True)
        voice_map = {item.voice.lower(): item.id for item in existing if item.voice and item.id}
        resolved_ids: list[UUID] = []
        for voice in request.voices:
            voice_id = voice_map.get(voice.lower())
            if voice_id:
                resolved_ids.append(voice_id)
            else:
                async with pool.acquire() as conn:
                    created = await create_voice(conn, voice, redis)
                resolved_ids.append(created.id)
        request.voice_ids = resolved_ids

    if request.qualities is not None and request.quality_ids is None:
        async with pool.acquire() as conn:
            existing = await search_qualities(conn, redis, search=None, limit_count=1000)
        quality_map = {item.quality.lower(): item.id for item in existing if item.quality and item.id}
        resolved_ids: list[UUID] = []
        for quality in request.qualities:
            quality_id = quality_map.get(quality.lower())
            if quality_id:
                resolved_ids.append(quality_id)
            else:
                errors.append(SaveAgentFieldError(field="qualities", message=f'Quality "{quality}" not found'))
        if not any(error.field == "qualities" for error in errors):
            request.quality_ids = resolved_ids

    # --- Inline prompt creation ---
    if request.prompt is not None and request.prompt_id is None and not errors:
        async with pool.acquire() as conn:
            result = await create_prompt(
                conn,
                system_prompt=request.prompt.system_prompt,
                name=request.prompt.name,
                description=request.prompt.description,
                redis=redis,
            )
        request.prompt_id = result.id

    return errors


async def patch_agent_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchAgentDraftApiRequest | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **kwargs: Any,
) -> PatchAgentDraftApiResponse:
    """Agent draft using canonical draft and DraftFormState flow."""

    if request is None:
        filtered = sanitize_model_kwargs(
            kwargs,
            list_fields={
                "departments",
                "department_ids",
                "tool_ids",
                "voice_ids",
                "voices",
                "quality_ids",
                "qualities",
                "rubric_ids",
                "flag_ids",
                "pending_ids",
            },
            bool_fields={"active"},
            drop_false_bools=set(),
            value_id_pairs=[
                ("name", "name_id"),
                ("description", "description_id"),
            ],
        )
        if draft_id:
            filtered["draft_id"] = draft_id
            filtered["input_draft_id"] = draft_id
        request = PatchAgentDraftApiRequest(**filtered)

    request.draft_id = request.draft_id or request.input_draft_id or draft_id
    request.input_draft_id = request.input_draft_id or request.draft_id
    idempotency_key = idempotency_key or request.idempotency_key
    if accept is None and idempotency_key is not None:
        accept = request.accept

    request.instructions_id = request.instructions_id or request.instruction_id
    request.instruction_id = request.instructions_id or request.instruction_id

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
            detail="You don't have permission to create or edit agent drafts.",
        )

    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                drafts = await get_agent_drafts(conn, [idempotency_key])
                async with conn.transaction():
                    if drafts:
                        draft = drafts[0]
                        await create_agent_draft(
                            conn,
                            session_id=session_id,
                            id=idempotency_key,
                            soft=False,
                            name_ids=draft.name_ids,
                            description_ids=draft.description_ids,
                            flag_ids=draft.flag_ids,
                            department_ids=draft.department_ids,
                            model_ids=draft.model_ids,
                            tool_ids=draft.tool_ids,
                            profile_ids=draft.profile_ids or [profile.profiles_id],
                            reasoning_level_ids=draft.reasoning_level_ids,
                            temperature_level_ids=draft.temperature_level_ids,
                            voice_ids=draft.voice_ids,
                            quality_ids=draft.quality_ids,
                            rubric_ids=draft.rubric_ids,
                            prompt_ids=draft.prompt_ids,
                            instruction_ids=draft.instruction_ids,
                            agent_ids=draft.agent_ids,
                            pending_ids=set(),
                        )
                    else:
                        await create_agent_draft(
                            conn,
                            session_id=session_id,
                            id=idempotency_key,
                            soft=False,
                            profile_ids=[profile.profiles_id],
                        )
            await refresh_agent_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                targets=["agent_drafts_mv"],
                operation_key=idempotency_key,
            )
        return PatchAgentDraftApiResponse(
            success=True,
            draft_id=idempotency_key,
            idempotency_key=idempotency_key,
            message="Draft accepted" if accept else "Draft rejected",
            form_state=DraftFormState(
                department_ids=[],
                tool_ids=[],
                voice_ids=[],
                quality_ids=[],
                rubric_ids=[],
                pending_ids=[],
            ),
        )

    errors = await _resolve_creatable_values(pool, redis, request)
    if errors:
        raise HTTPException(status_code=400, detail=[error.model_dump() for error in errors])

    request.flag_ids = _dedupe_ids(request.flag_ids)
    request.department_ids = _dedupe_ids(request.department_ids)
    request.tool_ids = _dedupe_ids(request.tool_ids)
    request.voice_ids = _dedupe_ids(request.voice_ids)
    request.quality_ids = _dedupe_ids(request.quality_ids)
    request.rubric_ids = _dedupe_ids(request.rubric_ids)


    async with pool.acquire() as conn:
        async with conn.transaction():
            snapshot_id: UUID | None = None
            if any(
                [
                    request.prompt_id,
                    request.instruction_id or request.instructions_id,
                    request.model_id,
                    request.tool_ids,
                    request.rubric_ids,
                    request.voice_ids,
                ]
            ):
                snapshot_id = await create_denormalized_snapshot(
                    pool,
                    redis,
                    name_id=request.name_id,
                    description_id=request.description_id,
                    department_ids=request.department_ids,
                    model_id=request.model_id,
                    prompt_id=request.prompt_id,
                    rubric_id=(request.rubric_ids or [None])[0],
                    tool_ids=request.tool_ids,
                    instruction_ids=[request.instruction_id or request.instructions_id]
                    if (request.instruction_id or request.instructions_id)
                    else None,
                    voice_ids=request.voice_ids,
                )
            result = await create_agent_draft(
                conn,
                session_id=session_id,
                id=idempotency_key or request.draft_id,
                soft=soft,
                name_ids=[request.name_id] if request.name_id else None,
                description_ids=[request.description_id] if request.description_id else None,
                flag_ids=request.flag_ids,
                department_ids=request.department_ids,
                model_ids=[request.model_id] if request.model_id else None,
                tool_ids=request.tool_ids,
                profile_ids=[profile.profiles_id],
                reasoning_level_ids=[request.reasoning_level_id] if request.reasoning_level_id else None,
                temperature_level_ids=[request.temperature_level_id] if request.temperature_level_id else None,
                voice_ids=request.voice_ids,
                quality_ids=request.quality_ids,
                rubric_ids=request.rubric_ids,
                prompt_ids=[request.prompt_id] if request.prompt_id else None,
                instruction_ids=[request.instruction_id or request.instructions_id]
                if (request.instruction_id or request.instructions_id)
                else None,
                agent_ids=[snapshot_id] if snapshot_id else None,
                pending_ids=set(request.pending_ids) if request.pending_ids else None,
            )

    # Re-derive denormalized flag bool from final flag_ids.
    echoed_active: bool | None = request.active
    if request.flag_ids:
        async with pool.acquire() as conn:
            selected_flags = await get_flags(conn, request.flag_ids, redis)
        for row in selected_flags:
            rtype = getattr(row, "type", None) or getattr(row, "name", None)
            rval = getattr(row, "value", None)
            if rtype == "agent_active":
                echoed_active = rval

    form_state = DraftFormState(
        name_id=request.name_id,
        name=request.name,
        description_id=request.description_id,
        description=request.description,
        flag_ids=request.flag_ids or [],
        active=echoed_active,
        department_ids=request.department_ids or [],
        model_id=request.model_id,
        tool_ids=request.tool_ids or [],
        reasoning_level_id=request.reasoning_level_id,
        temperature_level_id=request.temperature_level_id,
        voice_ids=request.voice_ids or [],
        quality_ids=request.quality_ids or [],
        rubric_ids=request.rubric_ids or [],
        prompt_id=request.prompt_id,
        instruction_id=request.instruction_id or request.instructions_id,
        pending_ids=request.pending_ids or [],
    )

    if not soft:
        await refresh_agent_impl(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            targets=["agent_drafts_mv"],
            operation_key=result.id,
        )

    return PatchAgentDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=result.id,
        message="Draft created (pending acceptance)" if soft else "Draft created successfully",
        form_state=form_state,
    )
