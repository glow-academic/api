"""Canonical shared department GET operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.group.resolve import resolve_group_impl
from app.infra.department.context import resolve_department_context
from app.infra.department.permissions import (
    DEPARTMENT_BASIC_RESOURCES,
    DEPARTMENT_RESOURCES,
    compute_can_draft,
    compute_can_edit,
    compute_description_required,
    compute_disabled_reason,
    compute_flag_required,
    compute_name_required,
    compute_settings_required,
    compute_show_description,
    compute_show_flag,
    compute_show_name,
    compute_show_settings,
    has_access,
)
from app.infra.department.permissions_context import resolve_department_permissions_context
from app.infra.department.types import (
    DepartmentDescriptionResource,
    DepartmentFlagConfig,
    DepartmentNameResource,
    DepartmentSettingResource,
    GetDepartmentApiResponse,
    SectionFilter,
)
from app.infra.helpers import dedupe_by_id
from app.infra.tool_graph import score_tools

SECTIONS = ["names", "descriptions", "flags", "settings"]


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


def _derive_flag_key_and_label(name: str | None) -> tuple[str, str]:
    if not name:
        return ("unknown", "Unknown")
    key = name.replace("department_", "")
    return (key, key.replace("_", " ").title())


async def get_department_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    id: UUID | None = None,
    department_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    filters: dict[str, SectionFilter | None] | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> GetDepartmentApiResponse:
    """Resolve the canonical department artifact bundle for any surface."""

    department_id = id or department_id
    resolved_filters = dict(filters or {})

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

    profile = common.profile
    if group_id is None:
        _gr = await resolve_group_impl(
            pool, redis,
            artifact_type="department",
            profile_id=profile_id,
            session_id=session_id,
            include_history=False,
        )
        group_id = _gr.group_id
    effective_group_id = group_id
    perms = None
    if department_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_department_permissions_context(conn, department_id)
        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Department {department_id} not found",
            )
        if not has_access(profile.role_level, profile.role_permissions):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this department.",
            )

    department = await resolve_department_context(
        pool,
        redis,
        department_id=department_id,
        group_id=effective_group_id,
        draft_id=draft_id,
        names_search=_sf(resolved_filters, "names", "search"),
        descriptions_search=_sf(resolved_filters, "descriptions", "search"),
        flags_search=_sf(resolved_filters, "flags", "search"),
        settings_search=_sf(resolved_filters, "settings", "search"),
        names_limit=_sf(resolved_filters, "names", "limit"),
        descriptions_limit=_sf(resolved_filters, "descriptions", "limit"),
        flags_limit=_sf(resolved_filters, "flags", "limit"),
        settings_limit=_sf(resolved_filters, "settings", "limit"),
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, DEPARTMENT_RESOURCES)
    include = {
        section: _sf(resolved_filters, section, "include") is not False
        for section in SECTIONS
    }
    selected_only = {
        section: bool(_sf(resolved_filters, section, "selected"))
        for section in SECTIONS
    }
    suggested_only = {
        section: bool(_sf(resolved_filters, section, "suggested"))
        for section in SECTIONS
    }

    usage_count = perms.usage_count if perms else 0
    can_edit = compute_can_edit(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
        usage_count=usage_count,
    )
    disabled_reason = compute_disabled_reason(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
        usage_count=usage_count,
    )

    pending_ids: set[UUID] = department.entries.get("pending_ids", set())

    names_selected = department.resources["names"].selected
    names_suggestions = department.resources["names"].suggestions
    descriptions_selected = department.resources["descriptions"].selected
    descriptions_suggestions = department.resources["descriptions"].suggestions
    flags_selected = department.resources["flags"].selected
    flags_suggestions = department.resources["flags"].suggestions
    settings_selected = department.resources["settings"].selected
    settings_suggestions = department.resources["settings"].suggestions

    all_names = dedupe_by_id(names_selected + names_suggestions)
    all_descriptions = dedupe_by_id(descriptions_selected + descriptions_suggestions)
    all_flags = dedupe_by_id(flags_selected + flags_suggestions)
    all_settings = dedupe_by_id(settings_selected + settings_suggestions)

    selected_ids = {
        "names": {item.id for item in names_selected if item.id},
        "descriptions": {item.id for item in descriptions_selected if item.id},
        "flags": {item.id for item in flags_selected if item.id},
        "settings": {item.id for item in settings_selected if item.id},
    }
    suggested_ids = {
        "names": {item.id for item in names_suggestions if item.id},
        "descriptions": {item.id for item in descriptions_suggestions if item.id},
        "flags": {item.id for item in flags_suggestions if item.id},
        "settings": {item.id for item in settings_suggestions if item.id},
    }

    show_flags_map = {
        "names": compute_show_name(scores.has_any.get("names", False)),
        "descriptions": compute_show_description(),
        "flags": compute_show_flag(),
        "settings": compute_show_settings(len(all_settings)),
    }
    required_flags_map = {
        "names": compute_name_required(),
        "descriptions": compute_description_required(),
        "flags": compute_flag_required(),
        "settings": compute_settings_required(),
    }

    def _decorate(item_id: UUID | None, section: str) -> tuple[bool, bool, bool]:
        return (
            bool(item_id and item_id in suggested_ids[section]),
            bool(item_id and item_id in selected_ids[section]),
            bool(item_id and item_id in pending_ids),
        )

    names = [
        DepartmentNameResource(
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
        DepartmentDescriptionResource(
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
        DepartmentFlagConfig(
            key=_derive_flag_key_and_label(getattr(item, "name", None) or getattr(item, "type", None))[0],
            label=_derive_flag_key_and_label(getattr(item, "name", None) or getattr(item, "type", None))[1],
            description=item.description,
            icon_id=getattr(item, "icon_id", None),

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
        if item.id
    ]
    settings = [
        DepartmentSettingResource(
            id=item.id,
            name=item.name,
            description=item.description,
            department_ids=item.department_ids or [],
            provider_key_ids=item.provider_key_ids or [],
            auth_ids=item.auth_ids or [],
            system_ids=item.system_ids or [],
            active=item.active,
            mcp=item.mcp,
            generated=item.generated,
            suggested=_decorate(item.id, "settings")[0],
            selected=_decorate(item.id, "settings")[1],
            pending=_decorate(item.id, "settings")[2],
        )
        for item in all_settings
    ]

    basic_show_ai_generate = compute_can_draft(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
    ) and any(scores.has_any.get(resource, False) for resource in DEPARTMENT_BASIC_RESOURCES)
    show_ai_generate = compute_can_draft(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
    ) and any(scores.has_any.get(resource, False) for resource in DEPARTMENT_RESOURCES)

    return GetDepartmentApiResponse(
        actor_name=profile.name,
        department_exists=department.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        group_id=effective_group_id,
        show_ai_generate=show_ai_generate,
        basic_show_ai_generate=basic_show_ai_generate,
        pending_ids=sorted(pending_ids),
        names=_filter_items(
            names,
            "names",
            selected_only=selected_only,
            suggested_only=suggested_only,
        ) if include["names"] else None,
        descriptions=_filter_items(
            descriptions,
            "descriptions",
            selected_only=selected_only,
            suggested_only=suggested_only,
        ) if include["descriptions"] else None,
        flags=_filter_items(
            flags,
            "flags",
            selected_only=selected_only,
            suggested_only=suggested_only,
        ) if include["flags"] else None,
        settings=_filter_items(
            settings,
            "settings",
            selected_only=selected_only,
            suggested_only=suggested_only,
        ) if include["settings"] else None,
    )
