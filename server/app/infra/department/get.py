"""Canonical shared department GET operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.department.context import resolve_department_context
from app.infra.department.permissions import (
    DEPARTMENT_BASIC_RESOURCES,
    DEPARTMENT_RESOURCES,
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
from app.infra.department.permissions_context import (
    resolve_department_permissions_context,
)
from app.infra.helpers import dedupe_by_id
from app.infra.tool_graph import score_tools
from app.infra.department.types import (
    DepartmentDescriptionSection,
    DepartmentFlagConfig,
    DepartmentFlagSection,
    DepartmentNameSection,
    DepartmentSettingSection,
    GetDepartmentApiResponse,
)


def derive_flag_key_and_label(name: str | None) -> tuple[str, str]:
    """Derive key and label from flag name like 'department_active' -> ('active', 'Active')."""
    if not name:
        return ("unknown", "Unknown")
    key = name.replace("department_", "")
    label = key.replace("_", " ").title()
    return (key, label)


async def get_department_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    department_id: UUID | None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    bypass_cache: bool = False,
) -> GetDepartmentApiResponse:
    """Resolve the canonical department response for any surface."""
    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        draft_id=draft_id,
        artifact_type="department",
        bypass_cache=bypass_cache,
    )
    if common is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    group_id = group_id or common.profile.group_id
    profile = common.profile

    perms = None
    if department_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_department_permissions_context(conn, department_id)
        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Department {department_id} not found",
            )
        if not has_access(profile.role):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this department.",
            )

    dept_ctx = await resolve_department_context(
        pool,
        redis,
        department_id=department_id,
        group_id=group_id,
        draft_id=draft_id,
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, DEPARTMENT_RESOURCES)
    agent_ids: dict[str, UUID | None] = {
        resource: (
            scores.best[resource].agent_id if scores.best.get(resource) else None
        )
        for resource in DEPARTMENT_RESOURCES
    }
    tool_ids_map: dict[str, UUID | None] = {
        resource: (scores.best[resource].tool_id if scores.best.get(resource) else None)
        for resource in DEPARTMENT_RESOURCES
    }

    usage_count = perms.usage_count if perms else 0
    can_edit = compute_can_edit(user_role=profile.role, usage_count=usage_count)
    disabled_reason = compute_disabled_reason(
        user_role=profile.role,
        usage_count=usage_count,
    )

    names_has_tools = scores.has_any.get("names", False)
    all_settings = dedupe_by_id(
        dept_ctx.resources["settings"].selected
        + dept_ctx.resources["settings"].suggestions,
        id_attr="id",
    )

    show_flags_map = {
        "names": compute_show_name(names_has_tools),
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
    show_ai_generate_map = {
        resource: (agent_ids.get(resource) is not None)
        for resource in DEPARTMENT_RESOURCES
    }
    basic_show_ai_generate = any(
        show_ai_generate_map.get(resource, False)
        for resource in DEPARTMENT_BASIC_RESOURCES
    )

    all_flags = dedupe_by_id(
        dept_ctx.resources["flags"].selected + dept_ctx.resources["flags"].suggestions
    )
    department_flags = [
        DepartmentFlagConfig(
            key=derive_flag_key_and_label(flag.name)[0],
            label=derive_flag_key_and_label(flag.name)[1],
            description=flag.description,
            icon_id=flag.icon,
            flag_option_id=flag.id,
            show=show_flags_map.get("flags", True),
            required=required_flags_map.get("flags", False),
            generated=flag.generated,
        )
        for flag in all_flags
        if flag.id
    ]
    current_flags = [
        DepartmentFlagConfig(
            key=derive_flag_key_and_label(flag.name)[0],
            label=derive_flag_key_and_label(flag.name)[1],
            description=flag.description,
            icon_id=flag.icon,
            flag_option_id=flag.id,
            show=show_flags_map.get("flags", True),
            required=required_flags_map.get("flags", False),
            generated=flag.generated,
        )
        for flag in dept_ctx.resources["flags"].selected
        if flag.id
    ]

    all_names = dedupe_by_id(
        dept_ctx.resources["names"].selected + dept_ctx.resources["names"].suggestions
    )
    all_descriptions = dedupe_by_id(
        dept_ctx.resources["descriptions"].selected
        + dept_ctx.resources["descriptions"].suggestions
    )

    suggestions_map = {
        "names": [item.id for item in dept_ctx.resources["names"].suggestions],
        "descriptions": [
            item.id for item in dept_ctx.resources["descriptions"].suggestions
        ],
        "settings": [],
    }

    if department_id is not None and not dept_ctx.resources["names"].selected:
        raise HTTPException(
            status_code=403,
            detail=(
                "You don't have access to this department. It may be restricted to "
                "other departments."
            ),
        )

    def _section(resource_key: str) -> dict:
        return {
            "show": show_flags_map.get(resource_key, False),
            "required": required_flags_map.get(resource_key, False),
            "suggestions": suggestions_map.get(resource_key, []),
            "show_ai_generate": show_ai_generate_map.get(resource_key, False),
            "tool_id": tool_ids_map.get(resource_key),
        }

    return GetDepartmentApiResponse(
        actor_name=profile.name,
        department_exists=dept_ctx.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        draft_version=dept_ctx.draft_version,
        group_id=group_id,
        basic_show_ai_generate=basic_show_ai_generate,
        names=DepartmentNameSection(
            resource=dept_ctx.resources["names"].selected[0]
            if dept_ctx.resources["names"].selected
            else None,
            resources=all_names,
            **_section("names"),
        ),
        descriptions=DepartmentDescriptionSection(
            resource=dept_ctx.resources["descriptions"].selected[0]
            if dept_ctx.resources["descriptions"].selected
            else None,
            resources=all_descriptions,
            **_section("descriptions"),
        ),
        flags=DepartmentFlagSection(
            current=current_flags or None,
            resources=department_flags,
            **_section("flags"),
        ),
        settings=DepartmentSettingSection(
            current=dept_ctx.resources["settings"].selected or None,
            resources=all_settings,
            **_section("settings"),
        ),
    )
