"""Canonical shared parameter GET operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.group.resolve import resolve_group_impl
from app.infra.helpers import dedupe_by_id
from app.infra.parameter.context import resolve_parameter_context
from app.infra.parameter.permissions import (
    PARAMETER_BASIC_RESOURCES,
    PARAMETER_FIELDS_RESOURCES,
    PARAMETER_RESOURCES,
    compute_can_draft,
    compute_can_edit,
    compute_disabled_reason,
    has_access,
)
from app.infra.parameter.permissions_context import (
    resolve_parameter_permissions_context,
)
from app.infra.parameter.types import (
    GetParameterApiResponse,
    ParameterDepartmentResource,
    ParameterDescriptionResource,
    ParameterFieldResource,
    ParameterFlagResource,
    ParameterNameResource,
    SectionFilter,
)
from app.infra.server_timing import timed
from app.infra.tool_graph import score_tools

SECTIONS = ["names", "descriptions", "flags", "departments", "parameter_fields"]


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


def _text_match(value: str | None, needle: str | None) -> bool:
    if not needle:
        return True
    return needle.lower() in (value or "").lower()


def _derive_flag_key_and_label(name: str | None) -> tuple[str, str]:
    if not name:
        return ("unknown", "Unknown")
    key = name.replace("parameter_", "")
    return (key, key.replace("_", " ").title())


async def get_parameter_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    id: UUID | None = None,
    parameter_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    filters: dict[str, SectionFilter | None] | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> GetParameterApiResponse:
    """Resolve the canonical parameter artifact bundle for any surface."""

    resolved_filters = dict(filters or {})
    if "parameter_fields" not in resolved_filters and resolved_filters.get("fields") is not None:
        resolved_filters["parameter_fields"] = resolved_filters["fields"]

    parameter_id = id or parameter_id

    raw_parameter_ids = _sf(resolved_filters, "parameter_fields", "parameter_ids")
    parameter_field_parameter_ids = [
        UUID(value) if isinstance(value, str) else value
        for value in (raw_parameter_ids or [])
    ] or None

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

    profile = common.profile
    if group_id is None:
        with timed("group"):
            _gr = await resolve_group_impl(
                pool, redis,
                artifact_type="parameter",
                profile_id=profile_id,
                session_id=session_id,
                include_history=False,
            )
            group_id = _gr.group_id
    effective_group_id = group_id
    perms = None
    if parameter_id is not None:
        with timed("permissions"):
            async with pool.acquire() as conn:
                perms = await resolve_parameter_permissions_context(conn, parameter_id)
        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Parameter {parameter_id} not found",
            )
        if not has_access(profile.role_level, profile.department_ids, perms.department_ids):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this parameter. It may be restricted to other departments.",
            )

    with timed("parameter_ctx"):
     parameter = await resolve_parameter_context(
        pool,
        redis,
        parameter_id=parameter_id,
        group_id=effective_group_id,
        draft_id=draft_id,
        user_department_ids=profile.department_ids,
        parameter_field_parameter_ids=parameter_field_parameter_ids,
        names_search=_sf(resolved_filters, "names", "search"),
        descriptions_search=_sf(resolved_filters, "descriptions", "search"),
        flags_search=_sf(resolved_filters, "flags", "search"),
        departments_search=_sf(resolved_filters, "departments", "search"),
        parameter_fields_search=_sf(resolved_filters, "parameter_fields", "search"),
        names_limit=_sf(resolved_filters, "names", "limit"),
        descriptions_limit=_sf(resolved_filters, "descriptions", "limit"),
        flags_limit=_sf(resolved_filters, "flags", "limit"),
        departments_limit=_sf(resolved_filters, "departments", "limit"),
        parameter_fields_limit=_sf(resolved_filters, "parameter_fields", "limit"),
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, PARAMETER_RESOURCES)
    include = {section: _sf(resolved_filters, section, "include") is not False for section in SECTIONS}
    selected_only = {section: bool(_sf(resolved_filters, section, "selected")) for section in SECTIONS}
    suggested_only = {section: bool(_sf(resolved_filters, section, "suggested")) for section in SECTIONS}

    can_edit = compute_can_edit(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
        parameter_department_ids=perms.department_ids if perms else [],
        active_scenario_count=perms.active_scenario_count if perms else 0,
        user_department_ids=profile.department_ids,
    )
    disabled_reason = compute_disabled_reason(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
        parameter_department_ids=perms.department_ids if perms else [],
        active_scenario_count=perms.active_scenario_count if perms else 0,
        user_department_ids=profile.department_ids,
    )

    can_draft = compute_can_draft(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
    )
    basic_show_ai_generate = can_draft and any(
        scores.has_any.get(resource, False) for resource in PARAMETER_BASIC_RESOURCES
    )
    fields_step_show_ai_generate = can_draft and any(
        scores.has_any.get(resource, False) for resource in PARAMETER_FIELDS_RESOURCES
    )

    pending_ids: set[UUID] = parameter.entries.get("pending_ids", set())

    names_selected = parameter.resources["names"].selected
    names_suggestions = parameter.resources["names"].suggestions
    descriptions_selected = parameter.resources["descriptions"].selected
    descriptions_suggestions = parameter.resources["descriptions"].suggestions
    flags_selected = parameter.resources["flags"].selected
    flags_suggestions = parameter.resources["flags"].suggestions
    departments_selected = parameter.resources["departments"].selected
    departments_suggestions = parameter.resources["departments"].suggestions
    parameter_fields_selected = parameter.resources["parameter_fields"].selected
    parameter_fields_suggestions = parameter.resources["parameter_fields"].suggestions

    all_names = dedupe_by_id(names_selected + names_suggestions)
    all_descriptions = dedupe_by_id(descriptions_selected + descriptions_suggestions)
    all_flags = dedupe_by_id(flags_selected + flags_suggestions)
    all_departments = dedupe_by_id(departments_selected + departments_suggestions)
    all_parameter_fields = dedupe_by_id(
        parameter_fields_selected + parameter_fields_suggestions
    )

    selected_ids = {
        "names": {item.id for item in names_selected if item.id},
        "descriptions": {item.id for item in descriptions_selected if item.id},
        "flags": {item.id for item in flags_selected if item.id},
        "departments": {item.id for item in departments_selected if item.id},
        "parameter_fields": {item.id for item in parameter_fields_selected if item.id},
    }
    suggested_ids = {
        "names": {item.id for item in names_suggestions if item.id},
        "descriptions": {item.id for item in descriptions_suggestions if item.id},
        "flags": {item.id for item in flags_suggestions if item.id},
        "departments": {item.id for item in departments_suggestions if item.id},
        "parameter_fields": {item.id for item in parameter_fields_suggestions if item.id},
    }

    field_lookup = parameter.entries.get("field_map", {})

    def _decorate_common(item_id: UUID | None, section: str) -> tuple[bool, bool, bool]:
        return (
            bool(item_id and item_id in suggested_ids[section]),
            bool(item_id and item_id in selected_ids[section]),
            bool(item_id and item_id in pending_ids),
        )

    def _names() -> list[ParameterNameResource]:
        items: list[ParameterNameResource] = []
        for item in all_names:
            suggested, selected, pending = _decorate_common(item.id, "names")
            items.append(
                ParameterNameResource(
                    id=item.id,
                    name=item.name,
                    generated=item.generated,
                    suggested=suggested,
                    selected=selected,
                    pending=pending,
                )
            )
        return items

    def _descriptions() -> list[ParameterDescriptionResource]:
        items: list[ParameterDescriptionResource] = []
        for item in all_descriptions:
            suggested, selected, pending = _decorate_common(item.id, "descriptions")
            items.append(
                ParameterDescriptionResource(
                    id=item.id,
                    description=item.description,
                    generated=item.generated,
                    suggested=suggested,
                    selected=selected,
                    pending=pending,
                )
            )
        return items

    def _flags() -> list[ParameterFlagResource]:
        items: list[ParameterFlagResource] = []
        for item in all_flags:
            if not item.id:
                continue
            suggested, selected, pending = _decorate_common(item.id, "flags")
            items.append(
                ParameterFlagResource(
                    id=item.id,
                    name=getattr(item, "name", None),
                    type=getattr(item, "type", None),
                    value=getattr(item, "value", None),
                    description=item.description,
                    icon_id=item.icon_id,
                    icon=getattr(item, "icon", None),
                    generated=item.generated,
                    suggested=suggested,
                    selected=selected,
                    pending=pending,
                )
            )
        return items

    def _departments() -> list[ParameterDepartmentResource]:
        items: list[ParameterDepartmentResource] = []
        for item in all_departments:
            suggested, selected, pending = _decorate_common(item.id, "departments")
            items.append(
                ParameterDepartmentResource(
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

    def _parameter_fields() -> list[ParameterFieldResource]:
        items: list[ParameterFieldResource] = []
        needle = _sf(resolved_filters, "parameter_fields", "search")
        for item in all_parameter_fields:
            field = field_lookup.get(item.field_id)
            if needle and not (
                _text_match(getattr(field, "name", None), needle)
                or _text_match(getattr(field, "description", None), needle)
            ):
                continue

            conditional_ids = list(getattr(field, "conditional_parameter_ids", []) or [])
            suggested, selected, pending = _decorate_common(item.id, "parameter_fields")
            items.append(
                ParameterFieldResource(
                    id=item.id,
                    field_id=item.field_id,
                    parameter_id=item.parameter_id,
                    name=getattr(field, "name", None),
                    description=getattr(field, "description", None),
                    conditional_parameter_id=conditional_ids[0] if conditional_ids else None,
                    generated=item.generated,
                    suggested=suggested,
                    selected=selected,
                    pending=pending,
                )
            )
        return items

    with timed("build"):
     return GetParameterApiResponse(
        actor_name=profile.name,
        parameter_exists=parameter.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        group_id=effective_group_id,
        # Draft label sourced from ``entries['draft_name']`` (set by
        # ``resolve_parameter_context``). ``None`` when no draft was active.
        draft_name=parameter.entries.get("draft_name") if parameter.entries else None,
        show_ai_generate=basic_show_ai_generate or fields_step_show_ai_generate,
        basic_show_ai_generate=basic_show_ai_generate,
        fields_step_show_ai_generate=fields_step_show_ai_generate,
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
        parameter_fields=_filter_items(
            _parameter_fields(),
            "parameter_fields",
            selected_only=selected_only,
            suggested_only=suggested_only,
        ) if include["parameter_fields"] else None,
    )
