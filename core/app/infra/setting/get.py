"""Canonical shared setting GET operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.common_context import resolve_common_context
from app.infra.helpers import dedupe_by_id
from app.infra.setting.context import resolve_setting_context
from app.infra.setting.permissions import (
    SETTING_GENERATION_RESOURCES,
    SETTING_RESOURCES,
    compute_auth_item_keys_required,
    compute_auths_required,
    compute_can_draft,
    compute_can_edit,
    compute_colors_required,
    compute_departments_required,
    compute_description_required,
    compute_disabled_reason,
    compute_flag_required,
    compute_name_required,
    compute_profiles_required,
    compute_provider_keys_required,
    compute_show_auth_item_keys,
    compute_show_auths,
    compute_show_colors,
    compute_show_departments,
    compute_show_description,
    compute_show_flag,
    compute_show_name,
    compute_show_profiles,
    compute_show_provider_keys,
    compute_show_systems,
    compute_systems_required,
    derive_flag_key_and_label,
    has_access,
)
from app.infra.setting.permissions_context import resolve_setting_permissions_context
from app.infra.setting.types import (
    GetSettingApiResponse,
    SectionFilter,
    SettingAuthItemKeyResource,
    SettingAuthResource,
    SettingColorResource,
    SettingDepartmentResource,
    SettingDescriptionResource,
    SettingFlagConfig,
    SettingKeyCatalogResource,
    SettingNameResource,
    SettingProfileResource,
    SettingProviderCatalogResource,
    SettingProviderKeyResource,
    SettingSystemResource,
)
from app.infra.tool_graph import score_tools

SECTIONS = [
    "names",
    "descriptions",
    "colors",
    "flags",
    "departments",
    "profiles",
    "auths",
    "provider_keys",
    "auth_item_keys",
    "systems",
]


def _sf(filters: dict[str, SectionFilter | None], section: str, attr: str, default=None):
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

    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        draft_id=draft_id,
        artifact_type="setting",
        bypass_cache=bypass_cache,
    )
    if common is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    actor = common.profile
    effective_group_id = group_id or actor.group_id

    perms = None
    if setting_id is not None:
        async with pool.acquire() as conn:
            perms = await resolve_setting_permissions_context(conn, setting_id)
        if not perms.exists:
            raise HTTPException(status_code=404, detail=f"Setting {setting_id} not found")
        if not has_access(actor.role_level, actor.department_ids, perms.department_ids):
            raise HTTPException(
                status_code=403,
                detail="You don't have access to this setting. It may be restricted to other departments.",
            )

    setting = await resolve_setting_context(
        pool,
        redis,
        setting_id=setting_id,
        group_id=effective_group_id,
        draft_id=draft_id,
        user_department_ids=actor.department_ids,
        owner_profile_id=actor.profiles_id,
        names_search=_sf(resolved_filters, "names", "search"),
        descriptions_search=_sf(resolved_filters, "descriptions", "search"),
        colors_search=_sf(resolved_filters, "colors", "search"),
        flags_search=_sf(resolved_filters, "flags", "search"),
        departments_search=_sf(resolved_filters, "departments", "search"),
        profiles_search=_sf(resolved_filters, "profiles", "search"),
        auths_search=_sf(resolved_filters, "auths", "search"),
        provider_keys_search=_sf(resolved_filters, "provider_keys", "search"),
        auth_item_keys_search=_sf(resolved_filters, "auth_item_keys", "search"),
        systems_search=_sf(resolved_filters, "systems", "search"),
        names_limit=_sf(resolved_filters, "names", "limit"),
        descriptions_limit=_sf(resolved_filters, "descriptions", "limit"),
        colors_limit=_sf(resolved_filters, "colors", "limit"),
        flags_limit=_sf(resolved_filters, "flags", "limit"),
        departments_limit=_sf(resolved_filters, "departments", "limit"),
        profiles_limit=_sf(resolved_filters, "profiles", "limit"),
        auths_limit=_sf(resolved_filters, "auths", "limit"),
        provider_keys_limit=_sf(resolved_filters, "provider_keys", "limit"),
        auth_item_keys_limit=_sf(resolved_filters, "auth_item_keys", "limit"),
        systems_limit=_sf(resolved_filters, "systems", "limit"),
        names_selected_only=_sf(resolved_filters, "names", "selected"),
        descriptions_selected_only=_sf(resolved_filters, "descriptions", "selected"),
        colors_selected_only=_sf(resolved_filters, "colors", "selected"),
        flags_selected_only=_sf(resolved_filters, "flags", "selected"),
        departments_selected_only=_sf(resolved_filters, "departments", "selected"),
        profiles_selected_only=_sf(resolved_filters, "profiles", "selected"),
        auths_selected_only=_sf(resolved_filters, "auths", "selected"),
        provider_keys_selected_only=_sf(resolved_filters, "provider_keys", "selected"),
        auth_item_keys_selected_only=_sf(resolved_filters, "auth_item_keys", "selected"),
        systems_selected_only=_sf(resolved_filters, "systems", "selected"),
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, SETTING_RESOURCES)
    include = {section: _sf(resolved_filters, section, "include") is not False for section in SECTIONS}
    selected_only = {section: bool(_sf(resolved_filters, section, "selected")) for section in SECTIONS}
    suggested_only = {section: bool(_sf(resolved_filters, section, "suggested")) for section in SECTIONS}

    perms_department_ids = perms.department_ids if perms else []
    can_edit = compute_can_edit(
        role_level=actor.role_level,
        role_permissions=actor.role_permissions,
        setting_department_ids=perms_department_ids,
        user_department_ids=actor.department_ids,
    )
    disabled_reason = compute_disabled_reason(
        role_level=actor.role_level,
        role_permissions=actor.role_permissions,
        setting_department_ids=perms_department_ids,
        user_department_ids=actor.department_ids,
    )

    pending_ids: set[UUID] = setting.entries.get("pending_ids", set())

    resource_pairs = setting.resources
    selected_ids = {
        section: {item.id for item in resource_pairs[section].selected if getattr(item, "id", None)}
        for section in resource_pairs
    }
    suggested_ids = {
        section: {item.id for item in resource_pairs[section].suggestions if getattr(item, "id", None)}
        for section in resource_pairs
    }

    def _decorate(item_id: UUID | None, section: str) -> tuple[bool, bool, bool]:
        return (
            bool(item_id and item_id in suggested_ids[section]),
            bool(item_id and item_id in selected_ids[section]),
            bool(item_id and item_id in pending_ids),
        )

    all_names = dedupe_by_id(resource_pairs["names"].selected + resource_pairs["names"].suggestions)
    all_descriptions = dedupe_by_id(resource_pairs["descriptions"].selected + resource_pairs["descriptions"].suggestions)
    all_colors = dedupe_by_id(resource_pairs["colors"].selected + resource_pairs["colors"].suggestions)
    all_flags = dedupe_by_id(resource_pairs["flags"].selected + resource_pairs["flags"].suggestions)
    all_departments = dedupe_by_id(resource_pairs["departments"].selected + resource_pairs["departments"].suggestions)
    all_profiles = dedupe_by_id(resource_pairs["profiles"].selected + resource_pairs["profiles"].suggestions)
    all_auths = dedupe_by_id(resource_pairs["auths"].selected + resource_pairs["auths"].suggestions)
    all_provider_keys = dedupe_by_id(resource_pairs["provider_keys"].selected + resource_pairs["provider_keys"].suggestions)
    all_auth_item_keys = dedupe_by_id(resource_pairs["auth_item_keys"].selected + resource_pairs["auth_item_keys"].suggestions)
    all_systems = dedupe_by_id(resource_pairs["systems"].selected + resource_pairs["systems"].suggestions)

    names = [
        SettingNameResource(
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
        SettingDescriptionResource(
            id=item.id,
            description=item.description,
            generated=item.generated,
            suggested=_decorate(item.id, "descriptions")[0],
            selected=_decorate(item.id, "descriptions")[1],
            pending=_decorate(item.id, "descriptions")[2],
        )
        for item in all_descriptions
    ]
    colors = [
        SettingColorResource(
            id=item.id,
            name=item.name,
            description=item.description,
            hex_code=item.hex_code,
            generated=item.generated,
            suggested=_decorate(item.id, "colors")[0],
            selected=_decorate(item.id, "colors")[1],
            pending=_decorate(item.id, "colors")[2],
        )
        for item in all_colors
    ]
    flags = [
        SettingFlagConfig(
            key=derive_flag_key_and_label(getattr(item, "name", None) or getattr(item, "type", None))[0],
            label=derive_flag_key_and_label(getattr(item, "name", None) or getattr(item, "type", None))[1],
            description=item.description,
            icon_id=getattr(item, "icon", None),
            flag_option_id=item.id,
            show=compute_show_flag(),
            required=compute_flag_required(),
            generated=item.generated,
            suggested=_decorate(item.id, "flags")[0],
            selected=_decorate(item.id, "flags")[1],
            pending=_decorate(item.id, "flags")[2],
        )
        for item in all_flags
        if item.id
    ]
    departments = [
        SettingDepartmentResource(
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
    profiles = [
        SettingProfileResource(
            profile_id=item.id,
            name=item.name,
            description=item.description,
            generated=item.generated,
            suggested=_decorate(item.id, "profiles")[0],
            selected=_decorate(item.id, "profiles")[1],
            pending=_decorate(item.id, "profiles")[2],
        )
        for item in all_profiles
    ]
    auths = [
        SettingAuthResource(
            auth_id=item.id,
            name=item.name,
            description=item.description,
            slug=item.slug,
            protocol=item.protocol,
            generated=item.generated,
            suggested=_decorate(item.id, "auths")[0],
            selected=_decorate(item.id, "auths")[1],
            pending=_decorate(item.id, "auths")[2],
        )
        for item in all_auths
    ]
    provider_keys = [
        SettingProviderKeyResource(
            id=item.id,
            provider_id=item.provider_id,
            key_id=item.key_id,
            key=item.key,
            name=item.name,
            description=item.description,
            generated=item.generated,
            suggested=_decorate(item.id, "provider_keys")[0],
            selected=_decorate(item.id, "provider_keys")[1],
            pending=_decorate(item.id, "provider_keys")[2],
        )
        for item in all_provider_keys
    ]
    auth_item_keys = [
        SettingAuthItemKeyResource(
            id=item.id,
            auth_id=item.auth_id,
            item_id=item.item_id,
            key_id=item.key_id,
            generated=item.generated,
            suggested=_decorate(item.id, "auth_item_keys")[0],
            selected=_decorate(item.id, "auth_item_keys")[1],
            pending=_decorate(item.id, "auth_item_keys")[2],
        )
        for item in all_auth_item_keys
    ]
    systems = [
        SettingSystemResource(
            system_id=item.id,
            name=item.name,
            description=item.description,
            agent_ids=item.agent_ids or [],
            resolution_strategy=item.resolution_strategy,
            resolution_threshold=item.resolution_threshold,
            generated=item.generated,
            suggested=_decorate(item.id, "systems")[0],
            selected=_decorate(item.id, "systems")[1],
            pending=_decorate(item.id, "systems")[2],
        )
        for item in all_systems
    ]

    providers_catalog = [
        SettingProviderCatalogResource(
            provider_id=item.id,
            name=item.name,
            description=item.description,
        )
        for item in setting.entries.get("providers", [])
    ]
    keys_catalog = [
        SettingKeyCatalogResource(
            key_id=item.id,
            name=item.name,
            description=item.description,
            masked_key=getattr(item, "key_masked", None) or getattr(item, "masked_key", None),
        )
        for item in setting.entries.get("keys", [])
    ]

    show_flags_map = {
        "names": compute_show_name(),
        "descriptions": compute_show_description(),
        "colors": compute_show_colors(len(all_colors)),
        "flags": compute_show_flag(),
        "departments": compute_show_departments(len(all_departments)),
        "profiles": compute_show_profiles(),
        "auths": compute_show_auths(),
        "provider_keys": compute_show_provider_keys(),
        "auth_item_keys": compute_show_auth_item_keys(),
        "systems": compute_show_systems(),
    }
    required_flags_map = {
        "names": compute_name_required(),
        "descriptions": compute_description_required(),
        "colors": compute_colors_required(),
        "flags": compute_flag_required(),
        "departments": compute_departments_required(show_flags_map["departments"]),
        "profiles": compute_profiles_required(),
        "auths": compute_auths_required(),
        "provider_keys": compute_provider_keys_required(),
        "auth_item_keys": compute_auth_item_keys_required(),
        "systems": compute_systems_required(),
    }

    basic_show_ai_generate = compute_can_draft(
        role_level=actor.role_level,
        role_permissions=actor.role_permissions,
    ) and any(scores.has_any.get(resource, False) for resource in SETTING_GENERATION_RESOURCES)
    show_ai_generate = compute_can_draft(
        role_level=actor.role_level,
        role_permissions=actor.role_permissions,
    ) and any(scores.has_any.get(resource, False) for resource in SETTING_RESOURCES)

    return GetSettingApiResponse(
        actor_name=actor.name,
        setting_exists=setting.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        group_id=effective_group_id,
        show_ai_generate=show_ai_generate,
        basic_show_ai_generate=basic_show_ai_generate,
        pending_ids=sorted(pending_ids),
        names=_filter_items(names, "names", selected_only=selected_only, suggested_only=suggested_only) if include["names"] else None,
        descriptions=_filter_items(descriptions, "descriptions", selected_only=selected_only, suggested_only=suggested_only) if include["descriptions"] else None,
        colors=_filter_items(colors, "colors", selected_only=selected_only, suggested_only=suggested_only) if include["colors"] else None,
        flags=_filter_items(flags, "flags", selected_only=selected_only, suggested_only=suggested_only) if include["flags"] else None,
        departments=_filter_items(departments, "departments", selected_only=selected_only, suggested_only=suggested_only) if include["departments"] else None,
        profiles=_filter_items(profiles, "profiles", selected_only=selected_only, suggested_only=suggested_only) if include["profiles"] else None,
        auths=_filter_items(auths, "auths", selected_only=selected_only, suggested_only=suggested_only) if include["auths"] else None,
        provider_keys=_filter_items(provider_keys, "provider_keys", selected_only=selected_only, suggested_only=suggested_only) if include["provider_keys"] else None,
        auth_item_keys=_filter_items(auth_item_keys, "auth_item_keys", selected_only=selected_only, suggested_only=suggested_only) if include["auth_item_keys"] else None,
        systems=_filter_items(systems, "systems", selected_only=selected_only, suggested_only=suggested_only) if include["systems"] else None,
        providers=providers_catalog,
        keys=keys_catalog,
    )
