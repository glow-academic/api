"""Canonical shared setting GET operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.group.resolve import resolve_group_impl
from app.infra.setting.context import resolve_setting_context
from app.infra.setting.permissions import SETTING_RESOURCES, has_access
from app.infra.setting.permissions_context import resolve_setting_permissions_context
from app.infra.setting.sections import SECTIONS, build_setting_get_result
from app.infra.setting.types import GetSettingApiResponse, SectionFilter
from app.infra.server_timing import timed
from app.infra.tool_graph import score_tools


def _sf(filters: dict[str, SectionFilter | None], section: str, attr: str, default=None):
    section_filter = filters.get(section)
    if section_filter is None:
        return default
    return getattr(section_filter, attr, default)


async def get_setting_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    id: UUID | None = None,
    setting_id: UUID | None = None,
    settings_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    filters: dict[str, SectionFilter | None] | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> GetSettingApiResponse:
    """Resolve the canonical setting artifact bundle for any surface."""

    resolved_filters = dict(filters or {})
    setting_id = id or setting_id or settings_id

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

    if group_id is None:
        with timed("group"):
            _gr = await resolve_group_impl(
                pool,
                redis,
                artifact_type="setting",
                profile_id=profile_id,
                session_id=session_id,
                include_history=False,
            )
            group_id = _gr.group_id
    effective_group_id = group_id

    actor = common.profile

    perms = None
    if setting_id is not None:
        with timed("permissions"):
            async with pool.acquire() as conn:
                perms = await resolve_setting_permissions_context(conn, setting_id)
        if not perms.exists:
            raise HTTPException(status_code=404, detail=f"Setting {setting_id} not found")
        if not has_access(actor.role_level, actor.department_ids, perms.department_ids):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this setting. It may be restricted to other departments.",
            )

    with timed("setting_ctx"):
     setting = await resolve_setting_context(
        pool,
        redis,
        setting_id=setting_id,
        group_id=effective_group_id,
        draft_id=draft_id,
        user_department_ids=actor.department_ids,
        names_search=_sf(resolved_filters, "names", "search"),
        descriptions_search=_sf(resolved_filters, "descriptions", "search"),
        colors_search=_sf(resolved_filters, "colors", "search"),
        flags_search=_sf(resolved_filters, "flags", "search"),
        departments_search=_sf(resolved_filters, "departments", "search"),
        logins_search=_sf(resolved_filters, "logins", "search"),
        systems_search=_sf(resolved_filters, "systems", "search"),
        mcp_search=_sf(resolved_filters, "mcp", "search"),
        thresholds_search=_sf(resolved_filters, "thresholds", "search"),
        provider_keys_search=_sf(resolved_filters, "provider_keys", "search"),
        auth_item_keys_search=_sf(resolved_filters, "auth_item_keys", "search"),
        auth_item_values_search=_sf(resolved_filters, "auth_item_values", "search"),
        names_limit=_sf(resolved_filters, "names", "limit"),
        descriptions_limit=_sf(resolved_filters, "descriptions", "limit"),
        colors_limit=_sf(resolved_filters, "colors", "limit"),
        flags_limit=_sf(resolved_filters, "flags", "limit"),
        departments_limit=_sf(resolved_filters, "departments", "limit"),
        logins_limit=_sf(resolved_filters, "logins", "limit"),
        systems_limit=_sf(resolved_filters, "systems", "limit"),
        mcp_limit=_sf(resolved_filters, "mcp", "limit"),
        thresholds_limit=_sf(resolved_filters, "thresholds", "limit"),
        provider_keys_limit=_sf(resolved_filters, "provider_keys", "limit"),
        auth_item_keys_limit=_sf(resolved_filters, "auth_item_keys", "limit"),
        auth_item_values_limit=_sf(resolved_filters, "auth_item_values", "limit"),
        names_selected_only=_sf(resolved_filters, "names", "selected"),
        descriptions_selected_only=_sf(resolved_filters, "descriptions", "selected"),
        colors_selected_only=_sf(resolved_filters, "colors", "selected"),
        flags_selected_only=_sf(resolved_filters, "flags", "selected"),
        departments_selected_only=_sf(resolved_filters, "departments", "selected"),
        logins_selected_only=_sf(resolved_filters, "logins", "selected"),
        systems_selected_only=_sf(resolved_filters, "systems", "selected"),
        mcp_selected_only=_sf(resolved_filters, "mcp", "selected"),
        thresholds_selected_only=_sf(resolved_filters, "thresholds", "selected"),
        provider_keys_selected_only=_sf(resolved_filters, "provider_keys", "selected"),
        auth_item_keys_selected_only=_sf(resolved_filters, "auth_item_keys", "selected"),
        auth_item_values_selected_only=_sf(resolved_filters, "auth_item_values", "selected"),
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, SETTING_RESOURCES)
    include = {s: _sf(resolved_filters, s, "include") is not False for s in SECTIONS}
    selected_only = {s: bool(_sf(resolved_filters, s, "selected")) for s in SECTIONS}
    suggested_only = {s: bool(_sf(resolved_filters, s, "suggested")) for s in SECTIONS}

    with timed("build"):
      return build_setting_get_result(
        common=common,
        setting=setting,
        scores=scores,
        perms=perms,
        group_id=effective_group_id,
        include=include,
        selected_only=selected_only,
        suggested_only=suggested_only,
    )
