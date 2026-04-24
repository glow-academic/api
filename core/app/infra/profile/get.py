"""Canonical shared profile GET operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.group.resolve import resolve_group_impl
from app.infra.helpers import dedupe_by_id
from app.infra.profile.context import resolve_profile_context
from app.infra.profile.permissions import (
    PROFILE_BASIC_RESOURCES,
    PROFILE_RESOURCES,
    compute_can_edit,
    compute_departments_required,
    compute_disabled_reason,
    compute_emails_required,
    compute_flag_required,
    compute_name_required,
    compute_role_options,
    compute_roles_required,
    compute_show_departments,
    compute_show_emails,
    compute_show_flag,
    compute_show_name,
    compute_show_roles,
    has_access,
)
from app.infra.profile.permissions_context import resolve_profile_permissions_context
from app.infra.profile.types import (
    GetProfileApiResponse,
    ProfileDepartmentResource,
    ProfileEmailResource,
    ProfileFlagResource,
    ProfileNameResource,
    ProfileRoleResource,
    SectionFilter,
)
from app.infra.tool_graph import score_tools
from app.tools.resources.colors.get import get_colors
from app.tools.resources.icons.get import get_icons

SECTIONS = ["names", "emails", "flags", "departments", "roles"]


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
    key = name.replace("profile_", "")
    return (key, key.replace("_", " ").title())


async def get_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    id: UUID | None = None,
    target_profile_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    filters: dict[str, SectionFilter | None] | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> GetProfileApiResponse:
    """Resolve the canonical profile artifact bundle for any surface."""

    resolved_filters = dict(filters or {})
    target_profile_id = id or target_profile_id

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
            artifact_type="profile",
            profile_id=profile_id,
            session_id=session_id,
            include_history=False,
        )
        group_id = _gr.group_id
    effective_group_id = group_id
    target_is_self = (
        target_profile_id is not None and profile_id == target_profile_id
    ) or target_profile_id is None

    perms = None
    if target_profile_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_profile_permissions_context(conn, target_profile_id)
        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Profile {target_profile_id} not found",
            )
        if not has_access(actor.role_level, actor.department_ids, perms.department_ids):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this profile. It may be restricted to other departments.",
            )

    profile_ctx = await resolve_profile_context(
        pool,
        redis,
        profile_id=target_profile_id,
        group_id=effective_group_id,
        draft_id=draft_id,
        user_department_ids=actor.department_ids,
        names_search=_sf(resolved_filters, "names", "search"),
        emails_search=_sf(resolved_filters, "emails", "search"),
        flags_search=_sf(resolved_filters, "flags", "search"),
        departments_search=_sf(resolved_filters, "departments", "search"),
        roles_search=_sf(resolved_filters, "roles", "search"),
        names_limit=_sf(resolved_filters, "names", "limit"),
        emails_limit=_sf(resolved_filters, "emails", "limit"),
        flags_limit=_sf(resolved_filters, "flags", "limit"),
        departments_limit=_sf(resolved_filters, "departments", "limit"),
        roles_limit=_sf(resolved_filters, "roles", "limit"),
        names_selected_only=_sf(resolved_filters, "names", "selected"),
        emails_selected_only=_sf(resolved_filters, "emails", "selected"),
        flags_selected_only=_sf(resolved_filters, "flags", "selected"),
        departments_selected_only=_sf(resolved_filters, "departments", "selected"),
        roles_selected_only=_sf(resolved_filters, "roles", "selected"),
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, PROFILE_RESOURCES)
    include = {section: _sf(resolved_filters, section, "include") is not False for section in SECTIONS}
    selected_only = {section: bool(_sf(resolved_filters, section, "selected")) for section in SECTIONS}
    suggested_only = {section: bool(_sf(resolved_filters, section, "suggested")) for section in SECTIONS}

    perms_department_ids = perms.department_ids if perms else []
    can_edit = compute_can_edit(
        role_level=actor.role_level,
        role_permissions=actor.role_permissions,
        target_is_self=target_is_self,
        target_department_ids=perms_department_ids,
        user_department_ids=actor.department_ids,
    )
    disabled_reason = compute_disabled_reason(
        role_level=actor.role_level,
        role_permissions=actor.role_permissions,
        target_is_self=target_is_self,
        target_department_ids=perms_department_ids,
    )

    names_has_tools = scores.has_any.get("names", False)
    emails_has_tools = scores.has_any.get("emails", False)

    names_selected = profile_ctx.resources["names"].selected
    names_suggestions = profile_ctx.resources["names"].suggestions
    emails_selected = profile_ctx.resources["emails"].selected
    emails_suggestions = profile_ctx.resources["emails"].suggestions
    flags_selected = profile_ctx.resources["flags"].selected
    flags_suggestions = profile_ctx.resources["flags"].suggestions
    departments_selected = profile_ctx.resources["departments"].selected
    departments_suggestions = profile_ctx.resources["departments"].suggestions
    roles_selected = profile_ctx.resources["roles"].selected
    roles_suggestions = profile_ctx.resources["roles"].suggestions

    all_names = dedupe_by_id(names_selected + names_suggestions)
    all_emails = dedupe_by_id(emails_selected + emails_suggestions)
    all_flags = dedupe_by_id(flags_selected + flags_suggestions)
    all_departments = dedupe_by_id(
        departments_selected + departments_suggestions
    )
    allowed_role_names = set(
        compute_role_options(
            role_level=actor.role_level,
            all_roles=[
                {"name": role.name, "level": role.level}
                for role in dedupe_by_id(roles_selected + roles_suggestions)
                if role.name is not None and role.level is not None
            ],
        )
    )
    filtered_role_suggestions = [
        role
        for role in roles_suggestions
        if role.name in allowed_role_names
    ]
    all_roles = dedupe_by_id(roles_selected + filtered_role_suggestions)
    role_icon_by_id: dict[UUID, str] = {}
    role_color_by_id: dict[UUID, str] = {}
    role_icon_ids = [item.icon_id for item in all_roles if item.icon_id]
    role_color_ids = [item.color_id for item in all_roles if item.color_id]
    if role_icon_ids or role_color_ids:
        async with pool.acquire() as conn:
            if role_icon_ids:
                icons = await get_icons(
                    conn,
                    list(dict.fromkeys(role_icon_ids)),
                    redis,
                    bypass_cache=bypass_cache,
                )
                role_icon_by_id = {icon.id: icon.value for icon in icons}
            if role_color_ids:
                colors = await get_colors(
                    conn,
                    list(dict.fromkeys(role_color_ids)),
                    redis,
                    bypass_cache=bypass_cache,
                )
                role_color_by_id = {color.id: color.hex_code for color in colors}

    show_flags_map = {
        "names": compute_show_name(names_has_tools),
        "emails": compute_show_emails(emails_has_tools),
        "flags": compute_show_flag(),
        "departments": compute_show_departments(len(all_departments)),
        "roles": compute_show_roles(),
    }
    required_flags_map = {
        "names": compute_name_required(),
        "emails": compute_emails_required(),
        "flags": compute_flag_required(),
        "departments": compute_departments_required(),
        "roles": compute_roles_required(),
    }

    selected_ids = {
        "names": {item.id for item in names_selected if item.id},
        "emails": {item.id for item in emails_selected if item.id},
        "flags": {item.id for item in flags_selected if item.id},
        "departments": {item.id for item in departments_selected if item.id},
        "roles": {item.id for item in roles_selected if item.id},
    }
    suggested_ids = {
        "names": {item.id for item in names_suggestions if item.id},
        "emails": {item.id for item in emails_suggestions if item.id},
        "flags": {item.id for item in flags_suggestions if item.id},
        "departments": {item.id for item in departments_suggestions if item.id},
        "roles": {item.id for item in filtered_role_suggestions if item.id},
    }
    pending_ids: set[UUID] = profile_ctx.entries.get("pending_ids", set())

    def _decorate(item_id: UUID | None, section: str) -> tuple[bool, bool, bool]:
        return (
            bool(item_id and item_id in suggested_ids[section]),
            bool(item_id and item_id in selected_ids[section]),
            bool(item_id and item_id in pending_ids),
        )

    names = [
        ProfileNameResource(
            id=item.id,
            name=item.name,
            generated=item.generated,
            suggested=_decorate(item.id, "names")[0],
            selected=_decorate(item.id, "names")[1],
            pending=_decorate(item.id, "names")[2],
        )
        for item in all_names
    ]
    emails = [
        ProfileEmailResource(
            id=item.id,
            email=item.email,
            generated=item.generated,
            suggested=_decorate(item.id, "emails")[0],
            selected=_decorate(item.id, "emails")[1],
            pending=_decorate(item.id, "emails")[2],
        )
        for item in all_emails
    ]
    flags = [
        ProfileFlagResource(
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
        ProfileDepartmentResource(
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
    roles = [
        ProfileRoleResource(
            id=item.id,
            role=item.name,
            name=item.name,
            description=item.description,
            icon_id=item.icon_id,
            icon=role_icon_by_id.get(item.icon_id) if item.icon_id else None,
            icon_value=role_icon_by_id.get(item.icon_id) if item.icon_id else None,
            color_id=item.color_id,
            color_hex=role_color_by_id.get(item.color_id) if item.color_id else None,
            level=item.level,
            generated=item.generated,
            suggested=_decorate(item.id, "roles")[0],
            selected=_decorate(item.id, "roles")[1],
            pending=_decorate(item.id, "roles")[2],
        )
        for item in all_roles
    ]

    return GetProfileApiResponse(
        actor_name=actor.name,
        profile_exists=profile_ctx.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        group_id=effective_group_id,
        profile_id=target_profile_id,
        show_ai_generate=any(scores.has_any.get(resource, False) for resource in PROFILE_RESOURCES),
        basic_show_ai_generate=any(scores.has_any.get(resource, False) for resource in PROFILE_BASIC_RESOURCES),
        contact_show_ai_generate=scores.has_any.get("emails", False),
        pending_ids=sorted(pending_ids) if pending_ids else [],
        role_options=sorted(allowed_role_names),
        names=_filter_items(names, "names", selected_only=selected_only, suggested_only=suggested_only)
        if include["names"]
        else None,
        emails=_filter_items(emails, "emails", selected_only=selected_only, suggested_only=suggested_only)
        if include["emails"]
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
        roles=_filter_items(roles, "roles", selected_only=selected_only, suggested_only=suggested_only)
        if include["roles"]
        else None,
    )
