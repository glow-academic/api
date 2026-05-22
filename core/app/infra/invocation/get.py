"""Canonical shared invocation GET operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.helpers import dedupe_by_id
from app.infra.invocation.context import resolve_invocation_context
from app.infra.server_timing import timed
from app.infra.invocation.types import (
    GetInvocationApiRequest,
    GetSuiteResponse,
    InvocationDepartmentResource,
    InvocationDescriptionResource,
    InvocationEndpointResource,
    InvocationFlagResource,
    InvocationKeyResource,
    InvocationModalityResource,
    InvocationNameResource,
    InvocationPricingResource,
    InvocationQualityResource,
    InvocationReasoningLevelResource,
    InvocationTemperatureLevelResource,
    InvocationValueResource,
    InvocationVoiceResource,
    SectionFilter,
)
INVOCATION_BUNDLE_RESOURCES: set[str] = {
    "names",
    "descriptions",
    "values",
    "flags",
    "departments",
    "keys",
    "endpoints",
    "modalities",
    "temperature_levels",
    "pricing",
    "reasoning_levels",
    "qualities",
    "voices",
}

SECTIONS = [
    "names",
    "descriptions",
    "values",
    "flags",
    "departments",
    "keys",
    "endpoints",
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


def _decorate(selected_items: list, suggestions: list, *, id_attr: str = "id") -> tuple[set[UUID], set[UUID]]:
    return (
        {getattr(item, id_attr, None) for item in selected_items if getattr(item, id_attr, None)},
        {getattr(item, id_attr, None) for item in suggestions if getattr(item, id_attr, None)},
    )


def _flag_key_and_label(name: str | None) -> tuple[str, str]:
    if not name:
        return ("unknown", "Unknown")
    key = name.replace("invocation_", "")
    return (key, key.replace("_", " ").title())


async def get_invocation_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    request: GetInvocationApiRequest | None = None,
    id: UUID | None = None,
    invocation_id: UUID | None = None,
    benchmark_bundle_entry_id: UUID | None = None,
    test_id: UUID | None = None,
    draft_id: UUID | None = None,
    filters: dict[str, SectionFilter | None] | None = None,
    bypass_cache: bool = False,
    descriptions_search: str | None = None,
    **_kwargs,
) -> GetSuiteResponse:
    """Resolve the canonical invocation editor bundle for any test-owned surface."""

    resolved_filters = dict(filters or {})
    if request is not None:
        invocation_id = (
            invocation_id
            or request.invocation_id
            or request.id
            or request.benchmark_bundle_entry_id
        )
        benchmark_bundle_entry_id = benchmark_bundle_entry_id or request.benchmark_bundle_entry_id
        test_id = test_id or request.test_id
        draft_id = draft_id or request.draft_id
        if "descriptions" not in resolved_filters and request.descriptions_search is not None:
            resolved_filters["descriptions"] = SectionFilter(search=request.descriptions_search)
        for section in SECTIONS:
            if section not in resolved_filters:
                resolved_filters[section] = getattr(request, section, None)

    invocation_id = invocation_id or id or benchmark_bundle_entry_id
    if "descriptions" not in resolved_filters and descriptions_search is not None:
        resolved_filters["descriptions"] = SectionFilter(search=descriptions_search)

    with timed("common"):
        common = await resolve_common_context(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            bypass_cache=bypass_cache,
        )
    if common is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # Invocation is test-scoped — use the canonical test group.
    from app.infra.test.group import group_test_impl
    with timed("group"):
        group_result = await group_test_impl(
            pool, redis,
            profile_id=profile_id,
            session_id=session_id,
            include_history=False,
        )
    group_id = group_result.group_id

    with timed("hydrate"):
     ctx = await resolve_invocation_context(
        pool,
        redis,
        group_id=group_id,
        invocation_id=invocation_id,
        draft_id=draft_id,
        user_department_ids=common.profile.department_ids,
        names_search=_sf(resolved_filters, "names", "search"),
        descriptions_search=_sf(resolved_filters, "descriptions", "search"),
        values_search=_sf(resolved_filters, "values", "search"),
        flags_search=_sf(resolved_filters, "flags", "search"),
        departments_search=_sf(resolved_filters, "departments", "search"),
        keys_search=_sf(resolved_filters, "keys", "search"),
        endpoints_search=_sf(resolved_filters, "endpoints", "search"),
        modalities_search=_sf(resolved_filters, "modalities", "search"),
        temperature_levels_search=_sf(resolved_filters, "temperature_levels", "search"),
        pricing_search=_sf(resolved_filters, "pricing", "search"),
        reasoning_levels_search=_sf(resolved_filters, "reasoning_levels", "search"),
        qualities_search=_sf(resolved_filters, "qualities", "search"),
        voices_search=_sf(resolved_filters, "voices", "search"),
        names_limit=_sf(resolved_filters, "names", "limit"),
        descriptions_limit=_sf(resolved_filters, "descriptions", "limit"),
        values_limit=_sf(resolved_filters, "values", "limit"),
        flags_limit=_sf(resolved_filters, "flags", "limit"),
        departments_limit=_sf(resolved_filters, "departments", "limit"),
        keys_limit=_sf(resolved_filters, "keys", "limit"),
        endpoints_limit=_sf(resolved_filters, "endpoints", "limit"),
        modalities_limit=_sf(resolved_filters, "modalities", "limit"),
        temperature_levels_limit=_sf(resolved_filters, "temperature_levels", "limit"),
        pricing_limit=_sf(resolved_filters, "pricing", "limit"),
        reasoning_levels_limit=_sf(resolved_filters, "reasoning_levels", "limit"),
        qualities_limit=_sf(resolved_filters, "qualities", "limit"),
        voices_limit=_sf(resolved_filters, "voices", "limit"),
        bypass_cache=bypass_cache,
    )

    selected_only = {section: bool(_sf(resolved_filters, section, "selected")) for section in SECTIONS}
    suggested_only = {section: bool(_sf(resolved_filters, section, "suggested")) for section in SECTIONS}
    include = {section: _sf(resolved_filters, section, "include") is not False for section in SECTIONS}
    pending_ids: set[UUID] = ctx.entries.get("pending_ids", set())

    names_selected = ctx.resources["names"].selected
    names_suggestions = ctx.resources["names"].suggestions
    descriptions_selected = ctx.resources["descriptions"].selected
    descriptions_suggestions = ctx.resources["descriptions"].suggestions
    values_selected = ctx.resources["values"].selected
    values_suggestions = ctx.resources["values"].suggestions
    flags_selected = ctx.resources["flags"].selected
    flags_suggestions = ctx.resources["flags"].suggestions
    departments_selected = ctx.resources["departments"].selected
    departments_suggestions = ctx.resources["departments"].suggestions
    keys_selected = ctx.resources["keys"].selected
    keys_suggestions = ctx.resources["keys"].suggestions
    endpoints_selected = ctx.resources["endpoints"].selected
    endpoints_suggestions = ctx.resources["endpoints"].suggestions
    modalities_selected = ctx.resources["modalities"].selected
    modalities_suggestions = ctx.resources["modalities"].suggestions
    temperature_selected = ctx.resources["temperature_levels"].selected
    temperature_suggestions = ctx.resources["temperature_levels"].suggestions
    pricing_selected = ctx.resources["pricing"].selected
    pricing_suggestions = ctx.resources["pricing"].suggestions
    reasoning_selected = ctx.resources["reasoning_levels"].selected
    reasoning_suggestions = ctx.resources["reasoning_levels"].suggestions
    qualities_selected = ctx.resources["qualities"].selected
    qualities_suggestions = ctx.resources["qualities"].suggestions
    voices_selected = ctx.resources["voices"].selected
    voices_suggestions = ctx.resources["voices"].suggestions

    names_selected_ids, names_suggested_ids = _decorate(names_selected, names_suggestions)
    descriptions_selected_ids, descriptions_suggested_ids = _decorate(descriptions_selected, descriptions_suggestions)
    values_selected_ids, values_suggested_ids = _decorate(values_selected, values_suggestions)
    flags_selected_ids, flags_suggested_ids = _decorate(flags_selected, flags_suggestions)
    departments_selected_ids, departments_suggested_ids = _decorate(departments_selected, departments_suggestions)
    keys_selected_ids, keys_suggested_ids = _decorate(keys_selected, keys_suggestions)
    endpoints_selected_ids, endpoints_suggested_ids = _decorate(endpoints_selected, endpoints_suggestions)
    modalities_selected_ids, modalities_suggested_ids = _decorate(modalities_selected, modalities_suggestions)
    temperature_selected_ids, temperature_suggested_ids = _decorate(temperature_selected, temperature_suggestions)
    pricing_selected_ids, pricing_suggested_ids = _decorate(pricing_selected, pricing_suggestions)
    reasoning_selected_ids, reasoning_suggested_ids = _decorate(reasoning_selected, reasoning_suggestions)
    qualities_selected_ids, qualities_suggested_ids = _decorate(qualities_selected, qualities_suggestions)
    voices_selected_ids, voices_suggested_ids = _decorate(voices_selected, voices_suggestions)

    names = [
        InvocationNameResource(
            id=item.id,
            name=item.name,
            generated=item.generated,
            suggested=bool(item.id and item.id in names_suggested_ids),
            selected=bool(item.id and item.id in names_selected_ids),
            pending=bool(item.id and item.id in pending_ids),
        )
        for item in dedupe_by_id(names_selected + names_suggestions)
    ]
    descriptions = [
        InvocationDescriptionResource(
            id=item.id,
            description=item.description,
            generated=item.generated,
            suggested=bool(item.id and item.id in descriptions_suggested_ids),
            selected=bool(item.id and item.id in descriptions_selected_ids),
            pending=bool(item.id and item.id in pending_ids),
        )
        for item in dedupe_by_id(descriptions_selected + descriptions_suggestions)
    ]
    values = [
        InvocationValueResource(
            id=item.id,
            value=item.value,
            type=getattr(item, "type", None),
            generated=item.generated,
            suggested=bool(item.id and item.id in values_suggested_ids),
            selected=bool(item.id and item.id in values_selected_ids),
            pending=bool(item.id and item.id in pending_ids),
        )
        for item in dedupe_by_id(values_selected + values_suggestions)
    ]
    flags = []
    for item in dedupe_by_id(flags_selected + flags_suggestions):
        if not item.id:
            continue
        flags.append(
            InvocationFlagResource(
                id=item.id,
                name=getattr(item, "name", None),
                type=getattr(item, "type", None),
                value=getattr(item, "value", None),
                description=item.description,
                icon_id=item.icon_id,
                icon=getattr(item, "icon", None),
                generated=item.generated,
                suggested=bool(item.id and item.id in flags_suggested_ids),
                selected=bool(item.id and item.id in flags_selected_ids),
                pending=bool(item.id and item.id in pending_ids),
            )
        )
    departments = [
        InvocationDepartmentResource(
            department_id=item.id,
            name=item.name,
            description=item.description,
            generated=item.generated,
            suggested=bool(item.id and item.id in departments_suggested_ids),
            selected=bool(item.id and item.id in departments_selected_ids),
            pending=bool(item.id and item.id in pending_ids),
        )
        for item in dedupe_by_id(departments_selected + departments_suggestions)
    ]
    keys = [
        InvocationKeyResource(
            id=item.id,
            key_id=item.id,
            name=item.name,
            description=item.description,
            key_masked=getattr(item, "key", None),
            masked_key=getattr(item, "key", None),
            active=item.active,
            generated=item.generated,
            suggested=bool(item.id and item.id in keys_suggested_ids),
            selected=bool(item.id and item.id in keys_selected_ids),
            pending=bool(item.id and item.id in pending_ids),
        )
        for item in dedupe_by_id(keys_selected + keys_suggestions)
    ]
    endpoints = [
        InvocationEndpointResource(
            id=item.id,
            base_url=item.base_url,
            generated=item.generated,
            suggested=bool(item.id and item.id in endpoints_suggested_ids),
            selected=bool(item.id and item.id in endpoints_selected_ids),
            pending=bool(item.id and item.id in pending_ids),
        )
        for item in dedupe_by_id(endpoints_selected + endpoints_suggestions)
    ]
    modalities = [
        InvocationModalityResource(
            id=item.id,
            modality_id=item.id,
            modality=item.modality,
            name=str(item.modality).replace("_", " ").title() if item.modality is not None else None,
            description=None,
            is_input=item.is_input,
            generated=item.generated,
            suggested=bool(item.id and item.id in modalities_suggested_ids),
            selected=bool(item.id and item.id in modalities_selected_ids),
            pending=bool(item.id and item.id in pending_ids),
        )
        for item in dedupe_by_id(modalities_selected + modalities_suggestions)
    ]
    temperature_levels = [
        InvocationTemperatureLevelResource(
            id=item.id,
            temperature=item.temperature,
            generated=item.generated,
            suggested=bool(item.id and item.id in temperature_suggested_ids),
            selected=bool(item.id and item.id in temperature_selected_ids),
            pending=bool(item.id and item.id in pending_ids),
        )
        for item in dedupe_by_id(temperature_selected + temperature_suggestions)
    ]
    pricing = [
        InvocationPricingResource(
            id=item.id,
            pricing_id=item.id,
            pricing_type=item.pricing_type,
            price=item.price,
            unit_name=item.unit_name,
            unit_category=item.unit_category,
            unit_value=item.unit_value,
            name=f"{item.pricing_type} {item.price}/{item.unit_name}",
            description=f"{item.unit_category} x{item.unit_value}",
            generated=item.generated,
            suggested=bool(item.id and item.id in pricing_suggested_ids),
            selected=bool(item.id and item.id in pricing_selected_ids),
            pending=bool(item.id and item.id in pending_ids),
        )
        for item in dedupe_by_id(pricing_selected + pricing_suggestions)
    ]
    reasoning_levels = [
        InvocationReasoningLevelResource(
            id=item.id,
            reasoning_level=item.reasoning_level,
            generated=item.generated,
            suggested=bool(item.id and item.id in reasoning_suggested_ids),
            selected=bool(item.id and item.id in reasoning_selected_ids),
            pending=bool(item.id and item.id in pending_ids),
        )
        for item in dedupe_by_id(reasoning_selected + reasoning_suggestions)
    ]
    qualities = [
        InvocationQualityResource(
            id=item.id,
            quality_id=item.id,
            quality=item.quality,
            generated=item.generated,
            suggested=bool(item.id and item.id in qualities_suggested_ids),
            selected=bool(item.id and item.id in qualities_selected_ids),
            pending=bool(item.id and item.id in pending_ids),
        )
        for item in dedupe_by_id(qualities_selected + qualities_suggestions)
    ]
    voices = [
        InvocationVoiceResource(
            id=item.id,
            voice=item.voice,
            generated=item.generated,
            suggested=bool(item.id and item.id in voices_suggested_ids),
            selected=bool(item.id and item.id in voices_selected_ids),
            pending=bool(item.id and item.id in pending_ids),
        )
        for item in dedupe_by_id(voices_selected + voices_suggestions)
    ]

    return GetSuiteResponse(
        actor_name=common.profile.name,
        test_id=test_id,
        invocation_id=invocation_id,
        profile_has_access=True,
        can_edit=True,
        disabled_reason=None,
        group_id=group_id,
        show_ai_generate=True,
        pending_ids=sorted(pending_ids) if pending_ids else [],
        names=_filter_items(names, "names", selected_only=selected_only, suggested_only=suggested_only) if include["names"] else None,
        descriptions=_filter_items(descriptions, "descriptions", selected_only=selected_only, suggested_only=suggested_only) if include["descriptions"] else None,
        values=_filter_items(values, "values", selected_only=selected_only, suggested_only=suggested_only) if include["values"] else None,
        flags=_filter_items(flags, "flags", selected_only=selected_only, suggested_only=suggested_only) if include["flags"] else None,
        departments=_filter_items(departments, "departments", selected_only=selected_only, suggested_only=suggested_only) if include["departments"] else None,
        keys=_filter_items(keys, "keys", selected_only=selected_only, suggested_only=suggested_only) if include["keys"] else None,
        endpoints=_filter_items(endpoints, "endpoints", selected_only=selected_only, suggested_only=suggested_only) if include["endpoints"] else None,
        modalities=_filter_items(modalities, "modalities", selected_only=selected_only, suggested_only=suggested_only) if include["modalities"] else None,
        temperature_levels=_filter_items(temperature_levels, "temperature_levels", selected_only=selected_only, suggested_only=suggested_only) if include["temperature_levels"] else None,
        pricing=_filter_items(pricing, "pricing", selected_only=selected_only, suggested_only=suggested_only) if include["pricing"] else None,
        reasoning_levels=_filter_items(reasoning_levels, "reasoning_levels", selected_only=selected_only, suggested_only=suggested_only) if include["reasoning_levels"] else None,
        qualities=_filter_items(qualities, "qualities", selected_only=selected_only, suggested_only=suggested_only) if include["qualities"] else None,
        voices=_filter_items(voices, "voices", selected_only=selected_only, suggested_only=suggested_only) if include["voices"] else None,
        # Invocation doesn't currently own a model picker; emit empty
        # catalogs so the canonical response shape matches eval.
        model_flags=[],
        model_flag_options=[],
    )
