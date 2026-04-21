"""Canonical shared field GET operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.group.resolve import resolve_group_impl
from app.infra.field.context import resolve_field_context
from app.infra.field.permissions import (
    FIELD_BASIC_RESOURCES,
    FIELD_RESOURCES,
    compute_can_draft,
    compute_can_edit,
    compute_disabled_reason,
    has_access,
)
from app.infra.field.permissions_context import resolve_field_permissions_context
from app.infra.helpers import dedupe_by_id
from app.infra.tool_graph import score_tools
from app.infra.field.types import (
    FieldConditionalParameterResource,
    FieldDepartmentResource,
    FieldDescriptionResource,
    FieldFlagConfig,
    FieldNameResource,
    GetFieldApiResponse,
    SectionFilter,
)

SECTIONS = ["names", "descriptions", "flags", "departments", "conditional_parameters"]


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
    key = name.replace("field_", "")
    return (key, key.replace("_", " ").title())


async def get_field_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    id: UUID | None = None,
    field_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    filters: dict[str, SectionFilter | None] | None = None,
    bypass_cache: bool = False,
    **legacy_kwargs,
) -> GetFieldApiResponse:
    """Resolve the canonical field artifact bundle for any surface."""

    resolved_filters = dict(filters or {})
    if "descriptions" not in resolved_filters and legacy_kwargs.get("descriptions_search") is not None:
        resolved_filters["descriptions"] = SectionFilter(
            search=legacy_kwargs["descriptions_search"]
        )
    if "conditional_parameters" not in resolved_filters and (
        legacy_kwargs.get("conditional_parameter_search") is not None
        or legacy_kwargs.get("conditional_parameter_show_selected") is not None
    ):
        resolved_filters["conditional_parameters"] = SectionFilter(
            search=legacy_kwargs.get("conditional_parameter_search"),
            selected=legacy_kwargs.get("conditional_parameter_show_selected"),
        )

    field_id = id or field_id

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
            artifact_type="field",
            profile_id=profile_id,
            session_id=session_id,
            include_history=False,
        )
        group_id = _gr.group_id
    effective_group_id = group_id
    perms = None
    if field_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_field_permissions_context(conn, field_id)
        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Field {field_id} not found",
            )
        if not has_access(profile.role_level, profile.department_ids, perms.department_ids):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this field. It may be restricted to other departments.",
            )

    field = await resolve_field_context(
        pool,
        redis,
        field_id=field_id,
        group_id=effective_group_id,
        draft_id=draft_id,
        user_department_ids=profile.department_ids,
        names_search=_sf(resolved_filters, "names", "search"),
        descriptions_search=_sf(resolved_filters, "descriptions", "search"),
        flags_search=_sf(resolved_filters, "flags", "search"),
        departments_search=_sf(resolved_filters, "departments", "search"),
        conditional_parameters_search=_sf(
            resolved_filters,
            "conditional_parameters",
            "search",
        ),
        names_limit=_sf(resolved_filters, "names", "limit"),
        descriptions_limit=_sf(resolved_filters, "descriptions", "limit"),
        flags_limit=_sf(resolved_filters, "flags", "limit"),
        departments_limit=_sf(resolved_filters, "departments", "limit"),
        conditional_parameters_limit=_sf(
            resolved_filters,
            "conditional_parameters",
            "limit",
        ),
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, FIELD_RESOURCES)
    include = {section: _sf(resolved_filters, section, "include") is not False for section in SECTIONS}
    selected_only = {section: bool(_sf(resolved_filters, section, "selected")) for section in SECTIONS}
    suggested_only = {section: bool(_sf(resolved_filters, section, "suggested")) for section in SECTIONS}

    can_edit = compute_can_edit(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
        field_department_ids=perms.department_ids if perms else [],
        active_parameter_count=perms.active_parameter_count if perms else 0,
        user_department_ids=profile.department_ids,
    )
    disabled_reason = compute_disabled_reason(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
        field_department_ids=perms.department_ids if perms else [],
        active_parameter_count=perms.active_parameter_count if perms else 0,
        user_department_ids=profile.department_ids,
    )

    basic_show_ai_generate = compute_can_draft(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
    ) and any(scores.has_any.get(resource, False) for resource in FIELD_BASIC_RESOURCES)

    pending_ids: set[UUID] = field.entries.get("pending_ids", set())

    names_selected = field.resources["names"].selected
    names_suggestions = field.resources["names"].suggestions
    descriptions_selected = field.resources["descriptions"].selected
    descriptions_suggestions = field.resources["descriptions"].suggestions
    flags_selected = field.resources["flags"].selected
    flags_suggestions = field.resources["flags"].suggestions
    departments_selected = field.resources["departments"].selected
    departments_suggestions = field.resources["departments"].suggestions
    conditional_parameters_selected = field.resources["conditional_parameters"].selected
    conditional_parameters_suggestions = field.resources["conditional_parameters"].suggestions

    all_names = dedupe_by_id(names_selected + names_suggestions)
    all_descriptions = dedupe_by_id(descriptions_selected + descriptions_suggestions)
    all_flags = dedupe_by_id(flags_selected + flags_suggestions)
    all_departments = dedupe_by_id(departments_selected + departments_suggestions)
    all_conditional_parameters = dedupe_by_id(
        conditional_parameters_selected + conditional_parameters_suggestions,
        id_attr="parameter_id",
    )

    selected_ids = {
        "names": {item.id for item in names_selected if item.id},
        "descriptions": {item.id for item in descriptions_selected if item.id},
        "flags": {item.id for item in flags_selected if item.id},
        "departments": {item.id for item in departments_selected if item.id},
        "conditional_parameters": {
            item.parameter_id
            for item in conditional_parameters_selected
            if item.parameter_id
        },
    }
    suggested_ids = {
        "names": {item.id for item in names_suggestions if item.id},
        "descriptions": {item.id for item in descriptions_suggestions if item.id},
        "flags": {item.id for item in flags_suggestions if item.id},
        "departments": {item.id for item in departments_suggestions if item.id},
        "conditional_parameters": {
            item.parameter_id
            for item in conditional_parameters_suggestions
            if item.parameter_id
        },
    }

    def _decorate_common(item_id: UUID | None, section: str) -> tuple[bool, bool, bool]:
        return (
            bool(item_id and item_id in suggested_ids[section]),
            bool(item_id and item_id in selected_ids[section]),
            bool(item_id and item_id in pending_ids),
        )

    def _names() -> list[FieldNameResource]:
        return [
            FieldNameResource(
                id=item.id,
                name=item.name,
                generated=item.generated,
                suggested=_decorate_common(item.id, "names")[0],
                selected=_decorate_common(item.id, "names")[1],
                pending=_decorate_common(item.id, "names")[2],
            )
            for item in all_names
        ]

    def _descriptions() -> list[FieldDescriptionResource]:
        return [
            FieldDescriptionResource(
                id=item.id,
                description=item.description,
                generated=item.generated,
                suggested=_decorate_common(item.id, "descriptions")[0],
                selected=_decorate_common(item.id, "descriptions")[1],
                pending=_decorate_common(item.id, "descriptions")[2],
            )
            for item in all_descriptions
        ]

    def _flags() -> list[FieldFlagConfig]:
        items: list[FieldFlagConfig] = []
        for item in all_flags:
            suggested, selected, pending = _decorate_common(item.id, "flags")
            key, label = _derive_flag_key_and_label(item.name)
            items.append(
                FieldFlagConfig(
                    key=key,
                    label=label,
                    description=item.description,
                    icon_id=str(item.icon_id) if item.icon_id else None,
                    flag_option_id=item.id,
                    show=True,
                    required=False,
                    generated=item.generated,
                    suggested=suggested,
                    selected=selected,
                    pending=pending,
                )
            )
        return items

    def _departments() -> list[FieldDepartmentResource]:
        items: list[FieldDepartmentResource] = []
        for item in all_departments:
            suggested, selected, pending = _decorate_common(item.id, "departments")
            items.append(
                FieldDepartmentResource(
                    department_id=item.id,
                    name=item.name,
                    description=item.description,
                    generated=item.generated,
                    suggested=suggested,
                    selected=selected,
                    pending=pending,
                )
            )
        return items

    def _conditional_parameters() -> list[FieldConditionalParameterResource]:
        items: list[FieldConditionalParameterResource] = []
        for item in all_conditional_parameters:
            suggested, selected, pending = _decorate_common(
                item.parameter_id,
                "conditional_parameters",
            )
            items.append(
                FieldConditionalParameterResource(
                    parameter_id=item.parameter_id,
                    name=item.name,
                    description=item.description,
                    generated=item.generated,
                    suggested=suggested,
                    selected=selected,
                    pending=pending,
                )
            )
        return items

    return GetFieldApiResponse(
        actor_name=profile.name,
        field_exists=field.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        group_id=effective_group_id,
        show_ai_generate=basic_show_ai_generate,
        basic_show_ai_generate=basic_show_ai_generate,
        pending_ids=list(pending_ids) or None,
        names=_filter_items(
            _names(),
            "names",
            selected_only=selected_only,
            suggested_only=suggested_only,
        ) if include["names"] else None,
        descriptions=_filter_items(
            _descriptions(),
            "descriptions",
            selected_only=selected_only,
            suggested_only=suggested_only,
        ) if include["descriptions"] else None,
        flags=_filter_items(
            _flags(),
            "flags",
            selected_only=selected_only,
            suggested_only=suggested_only,
        ) if include["flags"] else None,
        departments=_filter_items(
            _departments(),
            "departments",
            selected_only=selected_only,
            suggested_only=suggested_only,
        ) if include["departments"] else None,
        conditional_parameters=_filter_items(
            _conditional_parameters(),
            "conditional_parameters",
            selected_only=selected_only,
            suggested_only=suggested_only,
        ) if include["conditional_parameters"] else None,
    )
