"""Canonical shared model GET operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.group.resolve import resolve_group_impl
from app.infra.helpers import sorted_dedupe_by_id
from app.infra.model.context import resolve_model_context
from app.infra.model.permissions import (
    MODEL_BASIC_RESOURCES,
    MODEL_FEATURES_RESOURCES,
    MODEL_PROVIDER_RESOURCES,
    MODEL_RESOURCES,
    compute_can_edit,
    compute_departments_required,
    compute_description_required,
    compute_disabled_reason,
    compute_flag_required,
    compute_modalities_required,
    compute_name_required,
    compute_pricing_required,
    compute_provider_required,
    compute_qualities_required,
    compute_reasoning_levels_required,
    compute_show_departments,
    compute_show_description,
    compute_show_flag,
    compute_show_modalities,
    compute_show_name,
    compute_show_pricing,
    compute_show_provider,
    compute_show_qualities,
    compute_show_reasoning_levels,
    compute_show_temperature_levels,
    compute_show_value,
    compute_show_voices,
    compute_temperature_levels_required,
    compute_value_required,
    compute_voices_required,
    derive_flag_key_and_label,
    has_access,
)
from app.infra.model.permissions_context import resolve_model_permissions_context
from app.infra.model.types import (
    GetModelApiResponse,
    ModelDepartmentResource,
    ModelDescriptionResource,
    ModelFlagConfig,
    ModelModalityResource,
    ModelNameResource,
    ModelPricingResource,
    ModelProviderResource,
    ModelQualityResource,
    ModelReasoningLevelResource,
    ModelTemperatureLevelResource,
    ModelValueResource,
    ModelVoiceResource,
    SectionFilter,
)
from app.infra.tool_graph import score_tools

SECTIONS = [
    "names",
    "descriptions",
    "values",
    "providers",
    "flags",
    "departments",
    "modalities",
    "temperature_levels",
    "pricing",
    "reasoning_levels",
    "qualities",
    "voices",
]


def _sf(filters: dict[str, SectionFilter | None], section: str, attr: str, default=None):
    section_filter = filters.get(section)
    if section_filter is None:
        return default
    return getattr(section_filter, attr, default)


def _filter_items(items: list | None, section: str, *, selected_only: dict[str, bool], suggested_only: dict[str, bool]):
    if items is None:
        return None
    result = items
    if selected_only.get(section):
        result = [item for item in result if getattr(item, "selected", False)]
    if suggested_only.get(section):
        result = [item for item in result if getattr(item, "suggested", False)]
    return result


async def get_model_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    id: UUID | None = None,
    model_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    filters: dict[str, SectionFilter | None] | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> GetModelApiResponse:
    """Resolve the canonical model artifact bundle for any surface."""

    resolved_filters = dict(filters or {})
    model_id = id or model_id

    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        bypass_cache=bypass_cache,
    )
    if common is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    actor = common.profile
    if group_id is None:
        _gr = await resolve_group_impl(
            pool, redis,
            artifact_type="model",
            profile_id=profile_id,
            session_id=session_id,
            include_history=False,
        )
        group_id = _gr.group_id
    effective_group_id = group_id

    perms = None
    if model_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_model_permissions_context(conn, model_id)
        if not perms.exists:
            raise HTTPException(status_code=404, detail=f"Model {model_id} not found")
        if not has_access(actor.role_level, actor.department_ids, perms.department_ids):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this model. It may be restricted to other departments.",
            )

    model_ctx = await resolve_model_context(
        pool,
        redis,
        model_id=model_id,
        group_id=effective_group_id,
        draft_id=draft_id,
        user_department_ids=actor.department_ids,
        names_search=_sf(resolved_filters, "names", "search"),
        descriptions_search=_sf(resolved_filters, "descriptions", "search"),
        values_search=_sf(resolved_filters, "values", "search"),
        providers_search=_sf(resolved_filters, "providers", "search"),
        flags_search=_sf(resolved_filters, "flags", "search"),
        departments_search=_sf(resolved_filters, "departments", "search"),
        modalities_search=_sf(resolved_filters, "modalities", "search"),
        temperature_levels_search=_sf(resolved_filters, "temperature_levels", "search"),
        pricing_search=_sf(resolved_filters, "pricing", "search"),
        reasoning_levels_search=_sf(resolved_filters, "reasoning_levels", "search"),
        qualities_search=_sf(resolved_filters, "qualities", "search"),
        voices_search=_sf(resolved_filters, "voices", "search"),
        names_limit=_sf(resolved_filters, "names", "limit"),
        descriptions_limit=_sf(resolved_filters, "descriptions", "limit"),
        values_limit=_sf(resolved_filters, "values", "limit"),
        providers_limit=_sf(resolved_filters, "providers", "limit"),
        flags_limit=_sf(resolved_filters, "flags", "limit"),
        departments_limit=_sf(resolved_filters, "departments", "limit"),
        modalities_limit=_sf(resolved_filters, "modalities", "limit"),
        temperature_levels_limit=_sf(resolved_filters, "temperature_levels", "limit"),
        pricing_limit=_sf(resolved_filters, "pricing", "limit"),
        reasoning_levels_limit=_sf(resolved_filters, "reasoning_levels", "limit"),
        qualities_limit=_sf(resolved_filters, "qualities", "limit"),
        voices_limit=_sf(resolved_filters, "voices", "limit"),
        names_selected_only=_sf(resolved_filters, "names", "selected"),
        descriptions_selected_only=_sf(resolved_filters, "descriptions", "selected"),
        values_selected_only=_sf(resolved_filters, "values", "selected"),
        providers_selected_only=_sf(resolved_filters, "providers", "selected"),
        flags_selected_only=_sf(resolved_filters, "flags", "selected"),
        departments_selected_only=_sf(resolved_filters, "departments", "selected"),
        modalities_selected_only=_sf(resolved_filters, "modalities", "selected"),
        temperature_levels_selected_only=_sf(resolved_filters, "temperature_levels", "selected"),
        pricing_selected_only=_sf(resolved_filters, "pricing", "selected"),
        reasoning_levels_selected_only=_sf(resolved_filters, "reasoning_levels", "selected"),
        qualities_selected_only=_sf(resolved_filters, "qualities", "selected"),
        voices_selected_only=_sf(resolved_filters, "voices", "selected"),
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, MODEL_RESOURCES)
    include = {section: _sf(resolved_filters, section, "include") is not False for section in SECTIONS}
    selected_only = {section: bool(_sf(resolved_filters, section, "selected")) for section in SECTIONS}
    suggested_only = {section: bool(_sf(resolved_filters, section, "suggested")) for section in SECTIONS}

    perms_department_ids = perms.department_ids if perms else []
    active_agent_count = perms.active_agent_count if perms else 0
    can_edit = compute_can_edit(
        role_level=actor.role_level,
        role_permissions=actor.role_permissions,
        model_department_ids=perms_department_ids,
        active_agent_count=active_agent_count,
        user_department_ids=actor.department_ids,
    )
    disabled_reason = compute_disabled_reason(
        role_level=actor.role_level,
        role_permissions=actor.role_permissions,
        model_department_ids=perms_department_ids,
        active_agent_count=active_agent_count,
    )

    all_departments = sorted_dedupe_by_id(
        model_ctx.resources["departments"].suggestions + model_ctx.resources["departments"].selected
    )
    if model_id is None and not all_departments:
        raise HTTPException(status_code=400, detail="No accessible departments found for user")

    show_flags_map = {
        "names": compute_show_name(scores.has_any.get("names", False)),
        "descriptions": compute_show_description(),
        "values": compute_show_value(scores.has_any.get("values", False)),
        "providers": compute_show_provider(),
        "flags": compute_show_flag(),
        "departments": compute_show_departments(len(all_departments)),
        "modalities": compute_show_modalities(),
        "temperature_levels": compute_show_temperature_levels(),
        "pricing": compute_show_pricing(),
        "reasoning_levels": compute_show_reasoning_levels(),
        "qualities": compute_show_qualities(),
        "voices": compute_show_voices(),
    }
    required_flags_map = {
        "names": compute_name_required(),
        "descriptions": compute_description_required(),
        "values": compute_value_required(),
        "providers": compute_provider_required(),
        "flags": compute_flag_required(),
        "departments": compute_departments_required(),
        "modalities": compute_modalities_required(),
        "temperature_levels": compute_temperature_levels_required(),
        "pricing": compute_pricing_required(),
        "reasoning_levels": compute_reasoning_levels_required(),
        "qualities": compute_qualities_required(),
        "voices": compute_voices_required(),
    }

    basic_show_ai_generate = any(scores.has_any.get(resource, False) for resource in MODEL_BASIC_RESOURCES)
    provider_show_ai_generate = any(scores.has_any.get(resource, False) for resource in MODEL_PROVIDER_RESOURCES)
    features_show_ai_generate = any(scores.has_any.get(resource, False) for resource in MODEL_FEATURES_RESOURCES)

    names_selected = model_ctx.resources["names"].selected
    names_suggestions = model_ctx.resources["names"].suggestions
    descriptions_selected = model_ctx.resources["descriptions"].selected
    descriptions_suggestions = model_ctx.resources["descriptions"].suggestions
    values_selected = model_ctx.resources["values"].selected
    values_suggestions = model_ctx.resources["values"].suggestions
    providers_selected = model_ctx.resources["providers"].selected
    providers_suggestions = model_ctx.resources["providers"].suggestions
    flags_selected = model_ctx.resources["flags"].selected
    flags_suggestions = model_ctx.resources["flags"].suggestions
    departments_selected = model_ctx.resources["departments"].selected
    departments_suggestions = model_ctx.resources["departments"].suggestions
    modalities_selected = model_ctx.resources["modalities"].selected
    modalities_suggestions = model_ctx.resources["modalities"].suggestions
    temperature_levels_selected = model_ctx.resources["temperature_levels"].selected
    temperature_levels_suggestions = model_ctx.resources["temperature_levels"].suggestions
    pricing_selected = model_ctx.resources["pricing"].selected
    pricing_suggestions = model_ctx.resources["pricing"].suggestions
    reasoning_levels_selected = model_ctx.resources["reasoning_levels"].selected
    reasoning_levels_suggestions = model_ctx.resources["reasoning_levels"].suggestions
    qualities_selected = model_ctx.resources["qualities"].selected
    qualities_suggestions = model_ctx.resources["qualities"].suggestions
    voices_selected = model_ctx.resources["voices"].selected
    voices_suggestions = model_ctx.resources["voices"].suggestions

    all_names = sorted_dedupe_by_id(names_selected + names_suggestions)
    all_descriptions = sorted_dedupe_by_id(descriptions_selected + descriptions_suggestions)
    all_values = sorted_dedupe_by_id(values_selected + values_suggestions)
    all_providers = sorted_dedupe_by_id(providers_selected + providers_suggestions)
    all_flags = sorted_dedupe_by_id(flags_selected + flags_suggestions)
    all_departments = sorted_dedupe_by_id(departments_selected + departments_suggestions)
    all_modalities = sorted_dedupe_by_id(modalities_selected + modalities_suggestions)
    all_temperature_levels = sorted_dedupe_by_id(temperature_levels_selected + temperature_levels_suggestions)
    all_pricing = sorted_dedupe_by_id(pricing_selected + pricing_suggestions)
    all_reasoning_levels = sorted_dedupe_by_id(reasoning_levels_selected + reasoning_levels_suggestions)
    all_qualities = sorted_dedupe_by_id(qualities_selected + qualities_suggestions)
    all_voices = sorted_dedupe_by_id(voices_selected + voices_suggestions)

    selected_ids = {
        "names": {item.id for item in names_selected if item.id},
        "descriptions": {item.id for item in descriptions_selected if item.id},
        "values": {item.id for item in values_selected if item.id},
        "providers": {item.id for item in providers_selected if item.id},
        "flags": {item.id for item in flags_selected if item.id},
        "departments": {item.id for item in departments_selected if item.id},
        "modalities": {item.id for item in modalities_selected if item.id},
        "temperature_levels": {item.id for item in temperature_levels_selected if item.id},
        "pricing": {item.id for item in pricing_selected if item.id},
        "reasoning_levels": {item.id for item in reasoning_levels_selected if item.id},
        "qualities": {item.id for item in qualities_selected if item.id},
        "voices": {item.id for item in voices_selected if item.id},
    }
    suggested_ids = {
        "names": {item.id for item in names_suggestions if item.id},
        "descriptions": {item.id for item in descriptions_suggestions if item.id},
        "values": {item.id for item in values_suggestions if item.id},
        "providers": {item.id for item in providers_suggestions if item.id},
        "flags": {item.id for item in flags_suggestions if item.id},
        "departments": {item.id for item in departments_suggestions if item.id},
        "modalities": {item.id for item in modalities_suggestions if item.id},
        "temperature_levels": {item.id for item in temperature_levels_suggestions if item.id},
        "pricing": {item.id for item in pricing_suggestions if item.id},
        "reasoning_levels": {item.id for item in reasoning_levels_suggestions if item.id},
        "qualities": {item.id for item in qualities_suggestions if item.id},
        "voices": {item.id for item in voices_suggestions if item.id},
    }
    pending_ids: set[UUID] = model_ctx.entries.get("pending_ids", set())

    def _decorate(item_id: UUID | None, section: str) -> tuple[bool, bool, bool]:
        return (
            bool(item_id and item_id in suggested_ids[section]),
            bool(item_id and item_id in selected_ids[section]),
            bool(item_id and item_id in pending_ids),
        )

    names = [
        ModelNameResource(
            id=item.id,
            name=item.name,
            generated=item.generated,
            suggested=_decorate(item.id, "names")[0],
            selected=_decorate(item.id, "names")[1],
            pending=_decorate(item.id, "names")[2],
        )
        for item in all_names
    ]
    descriptions = [
        ModelDescriptionResource(
            id=item.id,
            description=item.description,
            generated=item.generated,
            suggested=_decorate(item.id, "descriptions")[0],
            selected=_decorate(item.id, "descriptions")[1],
            pending=_decorate(item.id, "descriptions")[2],
        )
        for item in all_descriptions
    ]
    values = [
        ModelValueResource(
            id=item.id,
            value=item.value,
            value_type=getattr(item, "type", None),
            generated=item.generated,
            suggested=_decorate(item.id, "values")[0],
            selected=_decorate(item.id, "values")[1],
            pending=_decorate(item.id, "values")[2],
        )
        for item in all_values
    ]
    providers = [
        ModelProviderResource(
            id=item.id,
            name=item.name,
            description=item.description,
            value=getattr(item, "value", None),
            base_url=getattr(item, "base_url", None),
            generated=item.generated,
            suggested=_decorate(item.id, "providers")[0],
            selected=_decorate(item.id, "providers")[1],
            pending=_decorate(item.id, "providers")[2],
        )
        for item in all_providers
    ]
    flags = [
        ModelFlagConfig(
            key=derive_flag_key_and_label(item.name)[0],
            label=derive_flag_key_and_label(item.name)[1],
            description=item.description,
            icon_id=item.icon_id,
            icon=getattr(item, "icon", None),
            flag_option_id=item.id,
            show=show_flags_map["flags"],
            required=required_flags_map["flags"],
            generated=item.generated,
            suggested=_decorate(item.id, "flags")[0],
            selected=_decorate(item.id, "flags")[1],
            pending=_decorate(item.id, "flags")[2],
        )
        for item in all_flags
    ]
    departments = [
        ModelDepartmentResource(
            department_id=item.id,
            name=item.name,
            description=item.description,
            generated=item.generated,
            suggested=_decorate(item.id, "departments")[0],
            selected=_decorate(item.id, "departments")[1],
            pending=_decorate(item.id, "departments")[2],
        )
        for item in all_departments
    ]
    modalities = [
        ModelModalityResource(
            id=item.id,
            modality=item.modality,
            is_input=item.is_input,
            generated=item.generated,
            suggested=_decorate(item.id, "modalities")[0],
            selected=_decorate(item.id, "modalities")[1],
            pending=_decorate(item.id, "modalities")[2],
        )
        for item in all_modalities
    ]
    temperature_levels = [
        ModelTemperatureLevelResource(
            id=item.id,
            temperature=str(item.temperature) if item.temperature is not None else None,
            generated=item.generated,
            suggested=_decorate(item.id, "temperature_levels")[0],
            selected=_decorate(item.id, "temperature_levels")[1],
            pending=_decorate(item.id, "temperature_levels")[2],
        )
        for item in all_temperature_levels
    ]
    pricing = [
        ModelPricingResource(
            id=item.id,
            pricing_type=item.pricing_type,
            price=float(item.price) if item.price is not None else None,
            unit_name=item.unit_name,
            unit_category=item.unit_category,
            unit_value=float(item.unit_value) if item.unit_value is not None else None,
            generated=item.generated,
            suggested=_decorate(item.id, "pricing")[0],
            selected=_decorate(item.id, "pricing")[1],
            pending=_decorate(item.id, "pricing")[2],
        )
        for item in all_pricing
    ]
    reasoning_levels = [
        ModelReasoningLevelResource(
            id=item.id,
            reasoning_level=item.reasoning_level,
            generated=item.generated,
            suggested=_decorate(item.id, "reasoning_levels")[0],
            selected=_decorate(item.id, "reasoning_levels")[1],
            pending=_decorate(item.id, "reasoning_levels")[2],
        )
        for item in all_reasoning_levels
    ]
    qualities = [
        ModelQualityResource(
            id=item.id,
            quality=item.quality,
            generated=item.generated,
            suggested=_decorate(item.id, "qualities")[0],
            selected=_decorate(item.id, "qualities")[1],
            pending=_decorate(item.id, "qualities")[2],
        )
        for item in all_qualities
    ]
    voices = [
        ModelVoiceResource(
            id=item.id,
            voice=item.voice,
            generated=item.generated,
            suggested=_decorate(item.id, "voices")[0],
            selected=_decorate(item.id, "voices")[1],
            pending=_decorate(item.id, "voices")[2],
        )
        for item in all_voices
    ]

    return GetModelApiResponse(
        actor_name=actor.name,
        model_exists=perms.exists if perms else (model_id is None),
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        group_id=model_ctx.group_id,
        model_id=model_ctx.artifact_id or model_id,
        show_ai_generate=basic_show_ai_generate or provider_show_ai_generate or features_show_ai_generate,
        basic_show_ai_generate=basic_show_ai_generate,
        provider_show_ai_generate=provider_show_ai_generate,
        features_show_ai_generate=features_show_ai_generate,
        pending_ids=sorted(pending_ids) if pending_ids else [],
        names=_filter_items(names, "names", selected_only=selected_only, suggested_only=suggested_only) if include["names"] else None,
        descriptions=_filter_items(descriptions, "descriptions", selected_only=selected_only, suggested_only=suggested_only) if include["descriptions"] else None,
        values=_filter_items(values, "values", selected_only=selected_only, suggested_only=suggested_only) if include["values"] else None,
        providers=_filter_items(providers, "providers", selected_only=selected_only, suggested_only=suggested_only) if include["providers"] else None,
        flags=_filter_items(flags, "flags", selected_only=selected_only, suggested_only=suggested_only) if include["flags"] else None,
        departments=_filter_items(departments, "departments", selected_only=selected_only, suggested_only=suggested_only) if include["departments"] else None,
        modalities=_filter_items(modalities, "modalities", selected_only=selected_only, suggested_only=suggested_only) if include["modalities"] else None,
        temperature_levels=_filter_items(temperature_levels, "temperature_levels", selected_only=selected_only, suggested_only=suggested_only) if include["temperature_levels"] else None,
        pricing=_filter_items(pricing, "pricing", selected_only=selected_only, suggested_only=suggested_only) if include["pricing"] else None,
        reasoning_levels=_filter_items(reasoning_levels, "reasoning_levels", selected_only=selected_only, suggested_only=suggested_only) if include["reasoning_levels"] else None,
        qualities=_filter_items(qualities, "qualities", selected_only=selected_only, suggested_only=suggested_only) if include["qualities"] else None,
        voices=_filter_items(voices, "voices", selected_only=selected_only, suggested_only=suggested_only) if include["voices"] else None,
    )
