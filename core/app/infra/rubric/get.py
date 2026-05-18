"""Canonical shared rubric GET operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.group.resolve import resolve_group_impl
from app.infra.helpers import dedupe_by_id
from app.infra.rubric.context import resolve_rubric_context
from app.infra.rubric.permissions import (
    RUBRIC_BASIC_RESOURCES,
    RUBRIC_CONTENT_RESOURCES,
    RUBRIC_RESOURCES,
    compute_can_edit,
    compute_departments_required,
    compute_description_required,
    compute_disabled_reason,
    compute_flag_required,
    compute_name_required,
    compute_points_required,
    compute_show_departments,
    compute_show_description,
    compute_show_flag,
    compute_show_name,
    compute_show_points,
    compute_show_standard_groups,
    compute_show_standards,
    compute_standard_groups_required,
    compute_standards_required,
    has_access,
)
from app.infra.rubric.permissions_context import resolve_rubric_permissions_context
from app.infra.rubric.types import (
    GetRubricApiResponse,
    RubricDepartmentResource,
    RubricDescriptionResource,
    RubricFlagResource,
    RubricNameResource,
    RubricPointResource,
    RubricStandardGroupResource,
    RubricStandardResource,
    SectionFilter,
)
from app.infra.tool_graph import score_tools

SECTIONS = [
    "names",
    "descriptions",
    "flags",
    "departments",
    "points",
    "standard_groups",
    "standards",
]


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


async def get_rubric_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    id: UUID | None = None,
    rubric_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    filters: dict[str, SectionFilter | None] | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> GetRubricApiResponse:
    """Resolve the canonical rubric artifact bundle for any surface."""

    rubric_id = id or rubric_id
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
            artifact_type="rubric",
            profile_id=profile_id,
            session_id=session_id,
            include_history=False,
        )
        group_id = _gr.group_id
    effective_group_id = group_id
    perms = None
    if rubric_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_rubric_permissions_context(conn, rubric_id)
        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Rubric {rubric_id} not found",
            )
        if not has_access(profile.role_level, profile.department_ids, perms.department_ids):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this rubric. It may be restricted to other departments.",
            )

    rubric = await resolve_rubric_context(
        pool,
        redis,
        rubric_id=rubric_id,
        group_id=effective_group_id,
        draft_id=draft_id,
        user_department_ids=profile.department_ids,
        names_search=_sf(resolved_filters, "names", "search"),
        descriptions_search=_sf(resolved_filters, "descriptions", "search"),
        flags_search=_sf(resolved_filters, "flags", "search"),
        departments_search=_sf(resolved_filters, "departments", "search"),
        points_search=_sf(resolved_filters, "points", "search"),
        standard_groups_search=_sf(resolved_filters, "standard_groups", "search"),
        standards_search=_sf(resolved_filters, "standards", "search"),
        names_limit=_sf(resolved_filters, "names", "limit"),
        descriptions_limit=_sf(resolved_filters, "descriptions", "limit"),
        flags_limit=_sf(resolved_filters, "flags", "limit"),
        departments_limit=_sf(resolved_filters, "departments", "limit"),
        points_limit=_sf(resolved_filters, "points", "limit"),
        standard_groups_limit=_sf(resolved_filters, "standard_groups", "limit"),
        standards_limit=_sf(resolved_filters, "standards", "limit"),
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, RUBRIC_RESOURCES)
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

    perms_department_ids = perms.department_ids if perms else []
    active_simulation_count = perms.active_simulation_count if perms else 0
    can_edit = compute_can_edit(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
        rubric_department_ids=perms_department_ids,
        active_simulation_count=active_simulation_count,
    )
    disabled_reason = compute_disabled_reason(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
        rubric_department_ids=perms_department_ids,
        active_simulation_count=active_simulation_count,
    )

    pending_ids: set[UUID] = rubric.entries.get("pending_ids", set())

    names_selected = rubric.resources["names"].selected
    names_suggestions = rubric.resources["names"].suggestions
    descriptions_selected = rubric.resources["descriptions"].selected
    descriptions_suggestions = rubric.resources["descriptions"].suggestions
    flags_selected = rubric.resources["flags"].selected
    flags_suggestions = rubric.resources["flags"].suggestions
    departments_selected = rubric.resources["departments"].selected
    departments_suggestions = rubric.resources["departments"].suggestions
    points_selected = rubric.resources["points"].selected
    points_suggestions = rubric.resources["points"].suggestions
    standard_groups_selected = rubric.resources["standard_groups"].selected
    standard_groups_suggestions = rubric.resources["standard_groups"].suggestions
    standards_selected = rubric.resources["standards"].selected
    standards_suggestions = rubric.resources["standards"].suggestions

    all_names = dedupe_by_id(names_selected + names_suggestions)
    all_descriptions = dedupe_by_id(descriptions_selected + descriptions_suggestions)
    all_flags = dedupe_by_id(flags_selected + flags_suggestions)
    all_departments = dedupe_by_id(departments_selected + departments_suggestions)
    all_points = dedupe_by_id(points_selected + points_suggestions)
    all_standard_groups = dedupe_by_id(
        standard_groups_selected + standard_groups_suggestions
    )
    all_standards = dedupe_by_id(standards_selected + standards_suggestions)

    if rubric_id is None and not all_departments:
        raise HTTPException(
            status_code=400,
            detail="No accessible departments found for user",
        )

    selected_ids = {
        "names": {item.id for item in names_selected if item.id},
        "descriptions": {item.id for item in descriptions_selected if item.id},
        "flags": {item.id for item in flags_selected if item.id},
        "departments": {item.id for item in departments_selected if item.id},
        "points": {item.id for item in points_selected if item.id},
        "standard_groups": {item.id for item in standard_groups_selected if item.id},
        "standards": {item.id for item in standards_selected if item.id},
    }
    suggested_ids = {
        "names": {item.id for item in names_suggestions if item.id},
        "descriptions": {item.id for item in descriptions_suggestions if item.id},
        "flags": {item.id for item in flags_suggestions if item.id},
        "departments": {item.id for item in departments_suggestions if item.id},
        "points": {item.id for item in points_suggestions if item.id},
        "standard_groups": {item.id for item in standard_groups_suggestions if item.id},
        "standards": {item.id for item in standards_suggestions if item.id},
    }

    show_flags_map = {
        "names": compute_show_name(scores.has_any.get("names", False)),
        "descriptions": compute_show_description(),
        "flags": compute_show_flag(),
        "departments": compute_show_departments(len(all_departments)),
        "points": compute_show_points(),
        "standard_groups": compute_show_standard_groups(),
        "standards": compute_show_standards(len(all_standard_groups)),
    }
    required_flags_map = {
        "names": compute_name_required(),
        "descriptions": compute_description_required(),
        "flags": compute_flag_required(),
        "departments": compute_departments_required(),
        "points": compute_points_required(),
        "standard_groups": compute_standard_groups_required(),
        "standards": compute_standards_required(),
    }

    def _decorate(item_id: UUID | None, section: str) -> tuple[bool, bool, bool]:
        return (
            bool(item_id and item_id in suggested_ids[section]),
            bool(item_id and item_id in selected_ids[section]),
            bool(item_id and item_id in pending_ids),
        )

    names = [
        RubricNameResource(
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
        RubricDescriptionResource(
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
        RubricFlagResource(
            id=item.id,
            name=getattr(item, "name", None),
            type=getattr(item, "type", None),
            value=getattr(item, "value", None),
            description=item.description,
            icon_id=item.icon_id,
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
        RubricDepartmentResource(
            department_id=item.id,
            id=item.id,
            name=item.name,
            description=item.description,
            department_ids=item.department_ids or [],
            setting_ids=item.setting_ids or [],
            generated=item.generated,
            suggested=_decorate(item.id, "departments")[0],
            selected=_decorate(item.id, "departments")[1],
            pending=_decorate(item.id, "departments")[2],
        )
        for item in all_departments
    ]
    # Split the points section by type: pass-type rows are user-writeable
    # (picker suggestions + selection), total-type is always computed from
    # the selected standards and exposed as a synthetic selected row so the
    # client can render a read-only display uniformly with the rest of the
    # resource-by-type pattern.
    pass_points = [
        RubricPointResource(
            id=item.id,
            value=item.value,
            type=item.type,
            generated=item.generated,
            suggested=_decorate(item.id, "points")[0],
            selected=_decorate(item.id, "points")[1],
            pending=_decorate(item.id, "points")[2],
        )
        for item in all_points
        if getattr(item, "type", None) == "pass"
    ]
    computed_total = sum(
        (getattr(s, "points", None) or 0)
        for s in standards_selected
    ) if standards_selected else 0
    total_synthetic = RubricPointResource(
        id=None,
        value=computed_total,
        type="total",
        generated=None,
        suggested=False,
        selected=True,
        pending=False,
    )
    points = [*pass_points, total_synthetic]
    standard_groups = [
        RubricStandardGroupResource(
            id=item.id,
            standard_group_id=item.id,
            name=item.name,
            short_name=item.short_name,
            description=item.description,
            points=item.points,
            pass_points=item.pass_points,
            generated=item.generated,
            suggested=_decorate(item.id, "standard_groups")[0],
            selected=_decorate(item.id, "standard_groups")[1],
            pending=_decorate(item.id, "standard_groups")[2],
        )
        for item in all_standard_groups
    ]
    standards = [
        RubricStandardResource(
            id=item.id,
            standard_id=item.id,
            standard_group_id=item.standard_group_id,
            name=item.name,
            description=item.description,
            points=item.points,
            generated=item.generated,
            suggested=_decorate(item.id, "standards")[0],
            selected=_decorate(item.id, "standards")[1],
            pending=_decorate(item.id, "standards")[2],
        )
        for item in all_standards
    ]

    basic_show_ai_generate = any(scores.has_any.get(resource, False) for resource in RUBRIC_BASIC_RESOURCES)
    content_show_ai_generate = any(scores.has_any.get(resource, False) for resource in RUBRIC_CONTENT_RESOURCES)

    return GetRubricApiResponse(
        actor_name=profile.name,
        rubric_exists=rubric.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        group_id=effective_group_id,
        # Draft label sourced from ``entries['draft_name']`` (set by
        # ``resolve_rubric_context``). ``None`` when no draft was active.
        draft_name=rubric.entries.get("draft_name") if rubric.entries else None,
        show_ai_generate=basic_show_ai_generate or content_show_ai_generate,
        basic_show_ai_generate=basic_show_ai_generate,
        content_show_ai_generate=content_show_ai_generate,
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
        points=_filter_items(points, "points", selected_only=selected_only, suggested_only=suggested_only)
        if include["points"]
        else None,
        standard_groups=_filter_items(
            standard_groups,
            "standard_groups",
            selected_only=selected_only,
            suggested_only=suggested_only,
        )
        if include["standard_groups"]
        else None,
        standards=_filter_items(
            standards,
            "standards",
            selected_only=selected_only,
            suggested_only=suggested_only,
        )
        if include["standards"]
        else None,
    )
