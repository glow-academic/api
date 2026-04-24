"""Canonical setting section assembly.

Pure/shared shaping for the setting artifact state. Transport-agnostic: HTTP,
MCP, CLI, and socket callers can all reuse it. Mirrors the persona/sections.py
pattern.
"""

from __future__ import annotations

from uuid import UUID

from app.infra.common_context import CommonContext
from app.infra.helpers import sorted_dedupe_by_id
from app.infra.setting.permissions import (
    SETTING_GENERATION_RESOURCES,
    SETTING_RESOURCES,
    compute_can_draft,
    compute_can_edit,
    compute_colors_required,
    compute_departments_required,
    compute_description_required,
    compute_disabled_reason,
    compute_flag_required,
    compute_name_required,
    compute_show_colors,
    compute_show_departments,
    compute_show_description,
    compute_show_flag,
    compute_show_name,
    derive_flag_key_and_label,
)
from app.infra.setting.permissions_context import SettingPermissionsContext
from app.infra.setting.types import (
    GetSettingApiResponse,
    SettingAgentCatalogResource,
    SettingAuthCatalogResource,
    SettingAuthItemKeyOption,
    SettingAuthItemKeyResource,
    SettingAuthItemValueOption,
    SettingAuthItemValueResource,
    SettingColorResource,
    SettingDepartmentResource,
    SettingDescriptionResource,
    SettingFlagResource,
    SettingIconCatalogResource,
    SettingItemCatalogResource,
    SettingKeyCatalogResource,
    SettingLoginsResource,
    SettingMcpOption,
    SettingMcpResource,
    SettingNameResource,
    SettingProfileCatalogResource,
    SettingProviderCatalogResource,
    SettingProviderKeyOption,
    SettingProviderKeyResource,
    SettingSystemResource,
    SettingThresholdResource,
)
from app.infra.tool_graph import ArtifactToolScores
from app.infra.types import ArtifactContext

SECTIONS = [
    "names",
    "descriptions",
    "colors",
    "flags",
    "departments",
    "logins",
    "systems",
    "mcp",
    "thresholds",
    "provider_keys",
    "auth_item_keys",
    "auth_item_values",
]


def build_setting_get_result(
    *,
    common: CommonContext,
    setting: ArtifactContext,
    scores: ArtifactToolScores,
    perms: SettingPermissionsContext | None,
    group_id: UUID | None,
    include: dict[str, bool] | None = None,
    selected_only: dict[str, bool] | None = None,
    suggested_only: dict[str, bool] | None = None,
) -> GetSettingApiResponse:
    """Build the canonical setting response bundle from resolved contexts."""
    inc = include or {}
    sel_only = selected_only or {}
    sug_only = suggested_only or {}

    def _filter_section(items: list | None, section: str) -> list | None:
        if items is None:
            return None
        if sel_only.get(section):
            items = [i for i in items if getattr(i, "selected", False)]
        if sug_only.get(section):
            items = [i for i in items if getattr(i, "suggested", False)]
        return items

    actor = common.profile
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
            bool(item_id and item_id in suggested_ids.get(section, set())),
            bool(item_id and item_id in selected_ids.get(section, set())),
            bool(item_id and item_id in pending_ids),
        )

    def _all(section: str) -> list:
        return sorted_dedupe_by_id(
            resource_pairs[section].suggestions + resource_pairs[section].selected
        )

    all_names = _all("names")
    all_descriptions = _all("descriptions")
    all_colors = _all("colors")
    all_flags = _all("flags")
    all_departments = _all("departments")
    all_logins = _all("logins")
    all_systems = _all("systems")
    all_mcp = _all("mcp")
    all_thresholds = _all("thresholds")
    all_provider_keys = _all("provider_keys")
    all_auth_item_keys = _all("auth_item_keys")
    # auth_item_values: selected only, no suggestions pool
    all_auth_item_values = list(resource_pairs["auth_item_values"].selected)

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
        SettingFlagResource(
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
    logins = [
        SettingLoginsResource(
            logins_id=item.id,
            profile_id=item.profile_id,
            auth_id=item.auth_id,
            icon_id=item.icon_id,
            icon=None,
            display_name=item.display_name,
            login_type=item.login_type,
            generated=item.generated,
            suggested=_decorate(item.id, "logins")[0],
            selected=_decorate(item.id, "logins")[1],
            pending=_decorate(item.id, "logins")[2],
        )
        for item in all_logins
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
    mcp = [
        SettingMcpResource(
            mcp_id=item.id,
            agent_id=item.agent_id,
            name=item.name,
            description=item.description,
            generated=item.generated,
            suggested=_decorate(item.id, "mcp")[0],
            selected=_decorate(item.id, "mcp")[1],
            pending=_decorate(item.id, "mcp")[2],
        )
        for item in all_mcp
    ]
    thresholds = [
        SettingThresholdResource(
            id=item.id,
            type=item.type,
            value=item.value,
            generated=item.generated,
            suggested=_decorate(item.id, "thresholds")[0],
            selected=_decorate(item.id, "thresholds")[1],
            pending=_decorate(item.id, "thresholds")[2],
        )
        for item in all_thresholds
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
    auth_item_values = [
        SettingAuthItemValueResource(
            id=item.id,
            auth_id=item.auth_id,
            item_id=item.item_id,
            value=item.value,
            generated=item.generated,
            suggested=False,
            selected=True,
            pending=item.id in pending_ids,
        )
        for item in all_auth_item_values
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
    items_catalog = [
        SettingItemCatalogResource(
            item_id=item.id,
            name=item.name,
            description=item.description,
            encrypted=item.encrypted,
            position=item.position,
        )
        for item in setting.entries.get("items", [])
    ]
    profiles_catalog = [
        SettingProfileCatalogResource(
            profile_id=item.id,
            name=item.name,
            description=item.description,
        )
        for item in setting.entries.get("profiles", [])
    ]
    auths_catalog = [
        SettingAuthCatalogResource(
            auth_id=item.id,
            name=item.name,
            description=item.description,
            slug=item.slug,
            protocol=item.protocol,
        )
        for item in setting.entries.get("auths", [])
    ]
    icons_catalog = [
        SettingIconCatalogResource(
            icon_id=item.id,
            name=item.name,
            description=item.description,
            value=item.value,
        )
        for item in setting.entries.get("icons", [])
    ]
    agents_catalog = [
        SettingAgentCatalogResource(
            agent_id=item.id,
            name=item.name,
            description=item.description,
        )
        for item in setting.entries.get("agents", [])
    ]

    provider_key_options = [
        SettingProviderKeyOption(
            provider_id=provider.id,
            key_id=key.id,
            provider_name=provider.name,
            key_name=key.name,
            masked_key=getattr(key, "key_masked", None) or getattr(key, "masked_key", None),
        )
        for provider in setting.entries.get("providers", [])
        if provider.id
        for key in setting.entries.get("keys", [])
        if key.id
    ]
    auth_item_key_options = [
        SettingAuthItemKeyOption(
            auth_id=auth.id,
            item_id=item.id,
            key_id=key.id,
            auth_name=auth.name,
            item_name=item.name,
            key_name=key.name,
            masked_key=getattr(key, "key_masked", None) or getattr(key, "masked_key", None),
        )
        for auth in setting.entries.get("auths", [])
        if auth.id
        for item in setting.entries.get("items", [])
        if item.id
        for key in setting.entries.get("keys", [])
        if key.id
    ]
    auth_item_value_options = [
        SettingAuthItemValueOption(
            auth_id=auth.id,
            item_id=item.id,
            auth_name=auth.name,
            item_name=item.name,
            item_description=item.description,
            encrypted=item.encrypted,
        )
        for auth in setting.entries.get("auths", [])
        if auth.id
        for item in setting.entries.get("items", [])
        if item.id
    ]
    mcp_options = [
        SettingMcpOption(
            agent_id=agent.id,
            agent_name=agent.name,
            agent_description=agent.description,
        )
        for agent in setting.entries.get("agents", [])
        if agent.id
    ]

    basic_show_ai_generate = compute_can_draft(
        role_level=actor.role_level,
        role_permissions=actor.role_permissions,
    ) and any(scores.has_any.get(resource, False) for resource in SETTING_GENERATION_RESOURCES)
    show_ai_generate = compute_can_draft(
        role_level=actor.role_level,
        role_permissions=actor.role_permissions,
    ) and any(scores.has_any.get(resource, False) for resource in SETTING_RESOURCES)

    def _section_or_none(items: list, section: str) -> list | None:
        if not inc.get(section, True):
            return None
        return _filter_section(items, section)

    # (show/required maps retained on the response only for sections that still surface them)
    _ = (
        compute_show_name(),
        compute_show_description(),
        compute_show_colors(len(all_colors)),
        compute_show_departments(len(all_departments)),
        compute_name_required(),
        compute_description_required(),
        compute_colors_required(),
        compute_departments_required(len(all_departments) > 0),
    )

    return GetSettingApiResponse(
        actor_name=actor.name,
        setting_exists=setting.artifact_id is not None,
        can_edit=can_edit,
        disabled_reason=disabled_reason,
        group_id=group_id,
        show_ai_generate=show_ai_generate,
        basic_show_ai_generate=basic_show_ai_generate,
        pending_ids=sorted(pending_ids),
        names=_section_or_none(names, "names"),
        descriptions=_section_or_none(descriptions, "descriptions"),
        colors=_section_or_none(colors, "colors"),
        flags=_section_or_none(flags, "flags"),
        departments=_section_or_none(departments, "departments"),
        logins=_section_or_none(logins, "logins"),
        systems=_section_or_none(systems, "systems"),
        mcp=_section_or_none(mcp, "mcp"),
        thresholds=_section_or_none(thresholds, "thresholds"),
        provider_keys=_section_or_none(provider_keys, "provider_keys"),
        auth_item_keys=_section_or_none(auth_item_keys, "auth_item_keys"),
        auth_item_values=_section_or_none(auth_item_values, "auth_item_values"),
        providers=providers_catalog,
        keys=keys_catalog,
        items=items_catalog,
        profiles=profiles_catalog,
        auths=auths_catalog,
        icons=icons_catalog,
        agents=agents_catalog,
        provider_key_options=provider_key_options,
        auth_item_key_options=auth_item_key_options,
        auth_item_value_options=auth_item_value_options,
        mcp_options=mcp_options,
    )
