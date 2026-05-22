"""Canonical shared provider GET operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.group.resolve import resolve_group_impl
from app.infra.helpers import dedupe_by_id
from app.infra.provider.context import resolve_provider_context
from app.infra.provider.permissions import (
    PROVIDER_BASIC_RESOURCES,
    PROVIDER_RESOURCES,
    compute_can_edit,
    compute_departments_required,
    compute_description_required,
    compute_disabled_reason,
    compute_endpoint_required,
    compute_flag_required,
    compute_key_required,
    compute_name_required,
    compute_show_departments,
    compute_show_description,
    compute_show_endpoint,
    compute_show_flag,
    compute_show_key,
    compute_show_name,
    compute_show_value,
    compute_value_required,
    has_access,
)
from app.infra.provider.permissions_context import (
    resolve_provider_permissions_context,
)
from app.infra.provider.types import (
    GetProviderApiResponse,
    ProviderDepartmentResource,
    ProviderDescriptionResource,
    ProviderEndpointResource,
    ProviderFlagResource,
    ProviderKeyResource,
    ProviderNameResource,
    ProviderValueResource,
    SectionFilter,
)
from app.infra.server_timing import timed
from app.infra.tool_graph import score_tools

SECTIONS = ["names", "descriptions", "flags", "departments", "values", "endpoints", "keys"]
PROVIDER_INTEGRATIONS_RESOURCES: set[str] = {"values", "endpoints"}


def _sf(
    filters: dict[str, SectionFilter | None],
    section: str,
    attr: str,
    default=None,
):
    section_filter = filters.get(section)
    if section_filter is None:
        return default
    return getattr(section_filter, attr, default)


def _filter_items(
    items: list | None,
    section: str,
    *,
    selected_only: dict[str, bool],
    suggested_only: dict[str, bool],
):
    if items is None:
        return None
    result = items
    if selected_only.get(section):
        result = [item for item in result if getattr(item, "selected", False)]
    if suggested_only.get(section):
        result = [item for item in result if getattr(item, "suggested", False)]
    return result


def derive_flag_key_and_label(name: str | None) -> tuple[str, str]:
    if not name:
        return ("unknown", "Unknown")
    key = name.replace("provider_", "")
    return (key, key.replace("_", " ").title())


async def get_provider_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    id: UUID | None = None,
    provider_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    filters: dict[str, SectionFilter | None] | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> GetProviderApiResponse:
    """Resolve the canonical provider artifact bundle for any surface."""

    resolved_filters = dict(filters or {})
    provider_id = id or provider_id

    with timed("common"):
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
        with timed("group"):
            _gr = await resolve_group_impl(
                pool, redis,
                artifact_type="provider",
                profile_id=profile_id,
                session_id=session_id,
                include_history=False,
            )
            group_id = _gr.group_id
    effective_group_id = group_id

    perms = None
    if provider_id is not None:
        with timed("permissions"):
            async with pool.acquire() as conn:
                perms = await resolve_provider_permissions_context(conn, provider_id)
        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Provider {provider_id} not found",
            )
        if not has_access(actor.role_level, actor.department_ids, perms.department_ids):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this provider. It may be restricted to other departments.",
            )

    with timed("provider_ctx"):
     provider_ctx = await resolve_provider_context(
        pool,
        redis,
        provider_id=provider_id,
        group_id=effective_group_id,
        draft_id=draft_id,
        user_department_ids=actor.department_ids,
        names_search=_sf(resolved_filters, "names", "search"),
        descriptions_search=_sf(resolved_filters, "descriptions", "search"),
        flags_search=_sf(resolved_filters, "flags", "search"),
        departments_search=_sf(resolved_filters, "departments", "search"),
        values_search=_sf(resolved_filters, "values", "search"),
        endpoints_search=_sf(resolved_filters, "endpoints", "search"),
        keys_search=_sf(resolved_filters, "keys", "search"),
        names_limit=_sf(resolved_filters, "names", "limit"),
        descriptions_limit=_sf(resolved_filters, "descriptions", "limit"),
        flags_limit=_sf(resolved_filters, "flags", "limit"),
        departments_limit=_sf(resolved_filters, "departments", "limit"),
        values_limit=_sf(resolved_filters, "values", "limit"),
        endpoints_limit=_sf(resolved_filters, "endpoints", "limit"),
        keys_limit=_sf(resolved_filters, "keys", "limit"),
        names_selected_only=_sf(resolved_filters, "names", "selected"),
        descriptions_selected_only=_sf(resolved_filters, "descriptions", "selected"),
        flags_selected_only=_sf(resolved_filters, "flags", "selected"),
        departments_selected_only=_sf(resolved_filters, "departments", "selected"),
        values_selected_only=_sf(resolved_filters, "values", "selected"),
        endpoints_selected_only=_sf(resolved_filters, "endpoints", "selected"),
        keys_selected_only=_sf(resolved_filters, "keys", "selected"),
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, PROVIDER_RESOURCES)
    include = {section: _sf(resolved_filters, section, "include") is not False for section in SECTIONS}
    selected_only = {section: bool(_sf(resolved_filters, section, "selected")) for section in SECTIONS}
    suggested_only = {section: bool(_sf(resolved_filters, section, "suggested")) for section in SECTIONS}

    perms_department_ids = perms.department_ids if perms else []
    active_model_count = perms.active_model_count if perms else 0

    can_edit = compute_can_edit(
        role_level=actor.role_level,
        role_permissions=actor.role_permissions,
        provider_department_ids=perms_department_ids,
        active_model_count=active_model_count,
        user_department_ids=actor.department_ids,
    )
    disabled_reason = compute_disabled_reason(
        role_level=actor.role_level,
        role_permissions=actor.role_permissions,
        provider_department_ids=perms_department_ids,
        active_model_count=active_model_count,
    )

    all_departments = dedupe_by_id(
        provider_ctx.resources["departments"].selected
        + provider_ctx.resources["departments"].suggestions
    )
    if provider_id is None and not all_departments:
        raise HTTPException(
            status_code=400,
            detail="No accessible departments found for user",
        )

    show_flags_map = {
        "names": compute_show_name(scores.has_any.get("names", False)),
        "descriptions": compute_show_description(),
        "flags": compute_show_flag(),
        "departments": compute_show_departments(len(all_departments)),
        "values": compute_show_value(),
        "endpoints": compute_show_endpoint(),
        "keys": compute_show_key(),
    }
    required_flags_map = {
        "names": compute_name_required(),
        "descriptions": compute_description_required(),
        "flags": compute_flag_required(),
        "departments": compute_departments_required(),
        "values": compute_value_required(),
        "endpoints": compute_endpoint_required(),
        "keys": compute_key_required(),
    }

    names_selected = provider_ctx.resources["names"].selected
    names_suggestions = provider_ctx.resources["names"].suggestions
    descriptions_selected = provider_ctx.resources["descriptions"].selected
    descriptions_suggestions = provider_ctx.resources["descriptions"].suggestions
    flags_selected = provider_ctx.resources["flags"].selected
    flags_suggestions = provider_ctx.resources["flags"].suggestions
    departments_selected = provider_ctx.resources["departments"].selected
    departments_suggestions = provider_ctx.resources["departments"].suggestions
    values_selected = provider_ctx.resources["values"].selected
    values_suggestions = provider_ctx.resources["values"].suggestions
    endpoints_selected = provider_ctx.resources["endpoints"].selected
    endpoints_suggestions = provider_ctx.resources["endpoints"].suggestions
    keys_selected = provider_ctx.resources["keys"].selected
    keys_suggestions = provider_ctx.resources["keys"].suggestions

    all_names = dedupe_by_id(names_selected + names_suggestions)
    all_descriptions = dedupe_by_id(descriptions_selected + descriptions_suggestions)
    all_flags = dedupe_by_id(flags_selected + flags_suggestions)
    all_departments = dedupe_by_id(departments_selected + departments_suggestions)
    all_values = dedupe_by_id(values_selected + values_suggestions)
    all_endpoints = dedupe_by_id(endpoints_selected + endpoints_suggestions)
    all_keys = dedupe_by_id(keys_selected + keys_suggestions)

    selected_ids = {
        "names": {item.id for item in names_selected if item.id},
        "descriptions": {item.id for item in descriptions_selected if item.id},
        "flags": {item.id for item in flags_selected if item.id},
        "departments": {item.id for item in departments_selected if item.id},
        "values": {item.id for item in values_selected if item.id},
        "endpoints": {item.id for item in endpoints_selected if item.id},
        "keys": {item.id for item in keys_selected if item.id},
    }
    suggested_ids = {
        "names": {item.id for item in names_suggestions if item.id},
        "descriptions": {item.id for item in descriptions_suggestions if item.id},
        "flags": {item.id for item in flags_suggestions if item.id},
        "departments": {item.id for item in departments_suggestions if item.id},
        "values": {item.id for item in values_suggestions if item.id},
        "endpoints": {item.id for item in endpoints_suggestions if item.id},
        "keys": {item.id for item in keys_suggestions if item.id},
    }
    pending_ids: set[UUID] = provider_ctx.entries.get("pending_ids", set())

    def _decorate(item_id: UUID | None, section: str) -> tuple[bool, bool, bool]:
        return (
            bool(item_id and item_id in suggested_ids[section]),
            bool(item_id and item_id in selected_ids[section]),
            bool(item_id and item_id in pending_ids),
        )

    names = [
        ProviderNameResource(
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
        ProviderDescriptionResource(
            id=item.id,
            description=item.description,
            generated=item.generated,
            suggested=_decorate(item.id, "descriptions")[0],
            selected=_decorate(item.id, "descriptions")[1],
            pending=_decorate(item.id, "descriptions")[2],
        )
        for item in all_descriptions
    ]
    flags = [
        ProviderFlagResource(
            id=item.id,
            name=getattr(item, "name", None),
            type=getattr(item, "type", None),
            value=getattr(item, "value", None),
            description=item.description,
            icon_id=getattr(item, "icon_id", None),
            icon=getattr(item, "icon", None),
            generated=item.generated,
            suggested=_decorate(item.id, "flags")[0],
            selected=_decorate(item.id, "flags")[1],
            pending=_decorate(item.id, "flags")[2],
        )
        for item in all_flags
        if item.id
    ]
    departments = [
        ProviderDepartmentResource(
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
    values = [
        ProviderValueResource(
            id=item.id,
            value=item.value,
            value_type=item.type,
            generated=item.generated,
            suggested=_decorate(item.id, "values")[0],
            selected=_decorate(item.id, "values")[1],
            pending=_decorate(item.id, "values")[2],
        )
        for item in all_values
    ]
    endpoints = [
        ProviderEndpointResource(
            id=item.id,
            base_url=item.base_url,
            generated=item.generated,
            suggested=_decorate(item.id, "endpoints")[0],
            selected=_decorate(item.id, "endpoints")[1],
            pending=_decorate(item.id, "endpoints")[2],
        )
        for item in all_endpoints
    ]
    keys = [
        ProviderKeyResource(
            id=item.id,
            key=item.key,
            name=item.name,
            description=item.description,
            generated=item.generated,
            suggested=_decorate(item.id, "keys")[0],
            selected=_decorate(item.id, "keys")[1],
            pending=_decorate(item.id, "keys")[2],
        )
        for item in all_keys
    ]

    with timed("build"):
     return GetProviderApiResponse(
        actor_name=actor.name,
        provider_exists=provider_ctx.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        group_id=provider_ctx.group_id,
        # Draft label sourced from ``entries['draft_name']`` (set by
        # ``resolve_provider_context``). ``None`` when no draft was active.
        draft_name=provider_ctx.entries.get("draft_name") if provider_ctx.entries else None,
        provider_id=provider_ctx.artifact_id,
        show_ai_generate=any(
            scores.has_any.get(resource, False)
            for resource in PROVIDER_BASIC_RESOURCES | PROVIDER_INTEGRATIONS_RESOURCES
        ),
        basic_show_ai_generate=any(
            scores.has_any.get(resource, False)
            for resource in PROVIDER_BASIC_RESOURCES
        ),
        integrations_show_ai_generate=any(
            scores.has_any.get(resource, False)
            for resource in PROVIDER_INTEGRATIONS_RESOURCES
        ),
        pending_ids=sorted(pending_ids),
        names=_filter_items(names, "names", selected_only=selected_only, suggested_only=suggested_only)
        if include["names"]
        else None,
        descriptions=_filter_items(
            descriptions,
            "descriptions",
            selected_only=selected_only,
            suggested_only=suggested_only,
        )
        if include["descriptions"]
        else None,
        flags=_filter_items(flags, "flags", selected_only=selected_only, suggested_only=suggested_only)
        if include["flags"]
        else None,
        departments=_filter_items(
            departments,
            "departments",
            selected_only=selected_only,
            suggested_only=suggested_only,
        )
        if include["departments"]
        else None,
        values=_filter_items(values, "values", selected_only=selected_only, suggested_only=suggested_only)
        if include["values"]
        else None,
        endpoints=_filter_items(
            endpoints,
            "endpoints",
            selected_only=selected_only,
            suggested_only=suggested_only,
        )
        if include["endpoints"]
        else None,
        keys=_filter_items(keys, "keys", selected_only=selected_only, suggested_only=suggested_only)
        if include["keys"]
        else None,
    )
