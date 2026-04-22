"""Canonical shared tool GET operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.group.resolve import resolve_group_impl
from app.infra.helpers import dedupe_by_id
from app.infra.tool.context import resolve_tool_context
from app.infra.tool.permissions import (
    compute_can_draft,
    compute_can_edit,
    compute_disabled_reason,
    compute_flag_required,
    compute_show_flag,
    has_access,
)
from app.infra.tool.permissions_context import resolve_tool_permissions_context
from app.infra.tool.types import (
    GetToolApiResponse,
    SectionFilter,
    ToolArgOutputResource,
    ToolArgPositionResource,
    ToolArgResource,
    ToolDescriptionResource,
    ToolFlagConfig,
    ToolNameResource,
    ToolPermissionResource,
)

SECTIONS = [
    "names",
    "descriptions",
    "flags",
    "args",
    "arg_positions",
    "args_outputs",
    "permissions",
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


def derive_flag_key_and_label(name: str | None) -> tuple[str, str]:
    if not name:
        return ("unknown", "Unknown")
    key = name.replace("tool_", "")
    return (key, key.replace("_", " ").title())


async def get_tool_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    id: UUID | None = None,
    tool_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    filters: dict[str, SectionFilter | None] | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> GetToolApiResponse:
    """Resolve the canonical tool artifact bundle for any surface."""

    resolved_filters = dict(filters or {})
    tool_id = id or tool_id

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
            artifact_type="tool",
            profile_id=profile_id,
            session_id=session_id,
            include_history=False,
        )
        group_id = _gr.group_id
    effective_group_id = group_id

    perms = None
    if tool_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_tool_permissions_context(conn, tool_id)
        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Tool {tool_id} not found",
            )
        if not has_access(actor.role_level):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this tool.",
            )

    tool_ctx = await resolve_tool_context(
        pool,
        redis,
        tool_id=tool_id,
        group_id=effective_group_id,
        draft_id=draft_id,
        names_search=_sf(resolved_filters, "names", "search"),
        descriptions_search=_sf(resolved_filters, "descriptions", "search"),
        flags_search=_sf(resolved_filters, "flags", "search"),
        args_search=_sf(resolved_filters, "args", "search"),
        arg_positions_search=_sf(resolved_filters, "arg_positions", "search"),
        args_outputs_search=_sf(resolved_filters, "args_outputs", "search"),
        permissions_search=_sf(resolved_filters, "permissions", "search"),
        names_limit=_sf(resolved_filters, "names", "limit"),
        descriptions_limit=_sf(resolved_filters, "descriptions", "limit"),
        flags_limit=_sf(resolved_filters, "flags", "limit"),
        args_limit=_sf(resolved_filters, "args", "limit"),
        arg_positions_limit=_sf(resolved_filters, "arg_positions", "limit"),
        args_outputs_limit=_sf(resolved_filters, "args_outputs", "limit"),
        permissions_limit=_sf(resolved_filters, "permissions", "limit"),
        names_selected_only=_sf(resolved_filters, "names", "selected"),
        descriptions_selected_only=_sf(resolved_filters, "descriptions", "selected"),
        flags_selected_only=_sf(resolved_filters, "flags", "selected"),
        args_selected_only=_sf(resolved_filters, "args", "selected"),
        arg_positions_selected_only=_sf(resolved_filters, "arg_positions", "selected"),
        args_outputs_selected_only=_sf(resolved_filters, "args_outputs", "selected"),
        permissions_selected_only=_sf(resolved_filters, "permissions", "selected"),
        bypass_cache=bypass_cache,
    )

    include = {section: _sf(resolved_filters, section, "include") is not False for section in SECTIONS}
    selected_only = {section: bool(_sf(resolved_filters, section, "selected")) for section in SECTIONS}
    suggested_only = {section: bool(_sf(resolved_filters, section, "suggested")) for section in SECTIONS}
    pending_ids = sorted(tool_ctx.entries.get("pending_ids", set()))

    active_agent_count = perms.active_agent_count if perms else 0
    can_edit = compute_can_edit(
        role_level=actor.role_level,
        role_permissions=actor.role_permissions,
        active_agent_count=active_agent_count,
    )
    disabled_reason = compute_disabled_reason(
        role_permissions=actor.role_permissions,
        active_agent_count=active_agent_count,
    )
    show_ai_generate = compute_can_draft(
        role_level=actor.role_level,
        role_permissions=actor.role_permissions,
    )

    names_selected = tool_ctx.resources["names"].selected
    names_suggestions = tool_ctx.resources["names"].suggestions
    descriptions_selected = tool_ctx.resources["descriptions"].selected
    descriptions_suggestions = tool_ctx.resources["descriptions"].suggestions
    flags_selected = tool_ctx.resources["flags"].selected
    flags_suggestions = tool_ctx.resources["flags"].suggestions
    args_selected = tool_ctx.resources["args"].selected
    args_suggestions = tool_ctx.resources["args"].suggestions
    arg_positions_selected = tool_ctx.resources["arg_positions"].selected
    arg_positions_suggestions = tool_ctx.resources["arg_positions"].suggestions
    args_outputs_selected = tool_ctx.resources["args_outputs"].selected
    args_outputs_suggestions = tool_ctx.resources["args_outputs"].suggestions
    permissions_selected = tool_ctx.resources["permissions"].selected
    permissions_suggestions = tool_ctx.resources["permissions"].suggestions

    all_names = dedupe_by_id(names_selected + names_suggestions)
    all_descriptions = dedupe_by_id(descriptions_selected + descriptions_suggestions)
    all_flags = dedupe_by_id(flags_selected + flags_suggestions)
    all_args = dedupe_by_id(args_selected + args_suggestions)
    all_arg_positions = dedupe_by_id(arg_positions_selected + arg_positions_suggestions)
    all_args_outputs = dedupe_by_id(args_outputs_selected + args_outputs_suggestions)
    all_permissions = dedupe_by_id(permissions_selected + permissions_suggestions)

    selected_ids = {
        "names": {item.id for item in names_selected if item.id},
        "descriptions": {item.id for item in descriptions_selected if item.id},
        "flags": {item.id for item in flags_selected if item.id},
        "args": {item.id for item in args_selected if item.id},
        "arg_positions": {item.id for item in arg_positions_selected if item.id},
        "args_outputs": {item.id for item in args_outputs_selected if item.id},
        "permissions": {item.id for item in permissions_selected if item.id},
    }
    suggested_ids = {
        "names": {item.id for item in names_suggestions if item.id},
        "descriptions": {item.id for item in descriptions_suggestions if item.id},
        "flags": {item.id for item in flags_suggestions if item.id},
        "args": {item.id for item in args_suggestions if item.id},
        "arg_positions": {item.id for item in arg_positions_suggestions if item.id},
        "args_outputs": {item.id for item in args_outputs_suggestions if item.id},
        "permissions": {item.id for item in permissions_suggestions if item.id},
    }

    arg_position_value_by_arg_id = {
        item.args_id: item.value for item in all_arg_positions if item.args_id is not None and item.value is not None
    }

    def _args_sort_key(item) -> tuple[int, str]:
        order = arg_position_value_by_arg_id.get(item.id, 10_000)
        return (order, item.name or "")

    all_args = sorted(all_args, key=_args_sort_key)

    def _pending(item_id: UUID | None) -> bool:
        return bool(item_id and item_id in pending_ids)

    names = [
        ToolNameResource(
            id=item.id,
            name=item.name,
            generated=item.generated,
            selected=item.id in selected_ids["names"],
            suggested=item.id in suggested_ids["names"],
            pending=_pending(item.id),
        )
        for item in all_names
    ]
    descriptions = [
        ToolDescriptionResource(
            id=item.id,
            description=item.description,
            generated=item.generated,
            selected=item.id in selected_ids["descriptions"],
            suggested=item.id in suggested_ids["descriptions"],
            pending=_pending(item.id),
        )
        for item in all_descriptions
    ]
    flags = [
        ToolFlagConfig(
            key=derive_flag_key_and_label(item.name)[0],
            label=derive_flag_key_and_label(item.name)[1],
            description=item.description,
            icon_id=item.icon_id,
            icon=getattr(item, "icon", None),
            flag_option_id=item.id,
            show=compute_show_flag(),
            required=compute_flag_required(),
            generated=item.generated,
            selected=item.id in selected_ids["flags"],
            suggested=item.id in suggested_ids["flags"],
            pending=_pending(item.id),
        )
        for item in all_flags
    ]
    args = [
        ToolArgResource(
            id=item.id,
            name=item.name,
            description=item.description,
            field_type=item.field_type,
            required=item.required,
            default_value=item.default_value,
            generated=item.generated,
            selected=item.id in selected_ids["args"],
            suggested=item.id in suggested_ids["args"],
            pending=_pending(item.id),
        )
        for item in all_args
    ]
    arg_positions = [
        ToolArgPositionResource(
            id=item.id,
            args_id=item.args_id,
            value=item.value,
            generated=item.generated,
            selected=item.id in selected_ids["arg_positions"],
            suggested=item.id in suggested_ids["arg_positions"],
            pending=_pending(item.id),
        )
        for item in sorted(
            all_arg_positions,
            key=lambda item: (item.value if item.value is not None else 10_000),
        )
    ]
    args_outputs = [
        ToolArgOutputResource(
            id=item.id,
            args_id=item.args_id,
            name=item.name,
            template=item.template,
            generated=item.generated,
            selected=item.id in selected_ids["args_outputs"],
            suggested=item.id in suggested_ids["args_outputs"],
            pending=_pending(item.id),
        )
        for item in all_args_outputs
    ]
    permissions = [
        ToolPermissionResource(
            id=item.id,
            artifact=str(item.artifact) if item.artifact is not None else None,
            operation=str(item.operation) if item.operation is not None else None,
            name=item.name,
            description=item.description,
            generated=item.generated,
            selected=item.id in selected_ids["permissions"],
            suggested=item.id in suggested_ids["permissions"],
            pending=_pending(item.id),
        )
        for item in all_permissions
    ]

    return GetToolApiResponse(
        actor_name=actor.name,
        tool_exists=tool_ctx.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        group_id=effective_group_id,
        tool_id=tool_ctx.artifact_id,
        show_ai_generate=show_ai_generate,
        basic_show_ai_generate=show_ai_generate,
        args_show_ai_generate=show_ai_generate,
        permissions_show_ai_generate=show_ai_generate,
        pending_ids=pending_ids,
        names=_filter_items(names, "names", selected_only=selected_only, suggested_only=suggested_only) if include["names"] else None,
        descriptions=_filter_items(descriptions, "descriptions", selected_only=selected_only, suggested_only=suggested_only) if include["descriptions"] else None,
        flags=_filter_items(flags, "flags", selected_only=selected_only, suggested_only=suggested_only) if include["flags"] else None,
        args=_filter_items(args, "args", selected_only=selected_only, suggested_only=suggested_only) if include["args"] else None,
        arg_positions=_filter_items(arg_positions, "arg_positions", selected_only=selected_only, suggested_only=suggested_only) if include["arg_positions"] else None,
        args_outputs=_filter_items(args_outputs, "args_outputs", selected_only=selected_only, suggested_only=suggested_only) if include["args_outputs"] else None,
        permissions=_filter_items(permissions, "permissions", selected_only=selected_only, suggested_only=suggested_only) if include["permissions"] else None,
    )
