"""Resolve setting artifact context — merged junctions + hydrated resources."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.flag_icons import hydrate_flag_icons
from app.infra.types import ArtifactContext, ResourcePair
from app.tools.artifacts.auth.get import get_auths as get_auth_artifacts
from app.tools.artifacts.auth.search import search_auths as search_auth_artifacts
from app.tools.artifacts.setting.get import get_settings as get_setting_artifacts
from app.tools.entries.setting_drafts.get import get_setting_drafts
from app.tools.resources.agents.search import search_agents
from app.tools.resources.auth_item_keys.get import get_auth_item_keys
from app.tools.resources.auth_item_keys.search import search_auth_item_keys
from app.tools.resources.auth_item_values.get import get_auth_item_values
from app.tools.resources.auths.search import search_auths
from app.tools.resources.colors.get import get_colors
from app.tools.resources.colors.search import search_colors
from app.tools.resources.departments.get import get_departments
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.search import search_flags
from app.tools.resources.icons.search import search_icons
from app.tools.resources.items.search import search_items
from app.tools.resources.keys.search import search_keys
from app.tools.resources.logins.get import get_logins
from app.tools.resources.logins.search import search_logins
from app.tools.resources.mcp.get import get_mcp
from app.tools.resources.mcp.search import search_mcp
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names
from app.tools.resources.profiles.search import search_profiles
from app.tools.resources.provider_keys.get import get_provider_keys
from app.tools.resources.provider_keys.search import search_provider_keys
from app.tools.resources.providers.search import search_providers
from app.tools.resources.systems.get import get_systems
from app.tools.resources.systems.search import search_systems
from app.tools.resources.thresholds.get import get_thresholds
from app.tools.resources.thresholds.search import search_thresholds

SETTING_FLAG_NAMES = {"setting_active", "mcp"}


@dataclass
class _MergedIds:
    name_ids: list[UUID]
    description_ids: list[UUID]
    color_ids: list[UUID]
    flag_ids: list[UUID]
    department_ids: list[UUID]
    logins_ids: list[UUID]
    systems_ids: list[UUID]
    mcp_ids: list[UUID]
    threshold_ids: list[UUID]
    provider_key_ids: list[UUID]
    auth_item_key_ids: list[UUID]
    auth_item_value_ids: list[UUID]
    auth_ids: list[UUID]
    provider_ids: list[UUID]


def _coalesce_limit(value: int | None, fallback: int) -> int:
    return value if value and value > 0 else fallback


def _selected_only(value: bool | None) -> bool:
    return bool(value)


def _merge_junction_ids(artifact: Any, draft: Any) -> _MergedIds:
    """Merge artifact junction IDs with draft overrides."""

    name_ids = list(artifact.name_ids or []) if artifact else []
    description_ids = list(artifact.description_ids or []) if artifact else []
    color_ids = list(artifact.color_ids or []) if artifact else []
    flag_ids = list(artifact.flag_ids or []) if artifact else []
    department_ids = list(artifact.department_ids or []) if artifact else []
    logins_ids = list(getattr(artifact, "logins_ids", None) or []) if artifact else []
    systems_ids = list(artifact.systems_ids or []) if artifact else []
    mcp_ids = list(getattr(artifact, "mcp_ids", None) or []) if artifact else []
    threshold_ids = list(getattr(artifact, "threshold_ids", None) or []) if artifact else []
    provider_key_ids = list(artifact.provider_key_ids or []) if artifact else []
    auth_item_key_ids = list(artifact.auth_item_keys_ids or []) if artifact else []
    auth_item_value_ids = list(getattr(artifact, "auth_item_value_ids", None) or []) if artifact else []
    auth_ids = list(getattr(artifact, "auth_ids", None) or []) if artifact else []
    provider_ids = list(getattr(artifact, "provider_ids", None) or []) if artifact else []

    if draft:
        if draft.name_ids:
            name_ids = list(draft.name_ids)
        if draft.description_ids:
            description_ids = list(draft.description_ids)
        if draft.color_ids:
            color_ids = list(draft.color_ids)
        if draft.flag_ids:
            flag_ids = list(draft.flag_ids)
        if draft.department_ids:
            department_ids = list(draft.department_ids)
        if getattr(draft, "logins_ids", None):
            logins_ids = list(draft.logins_ids)
        if draft.system_ids:
            systems_ids = list(draft.system_ids)
        if getattr(draft, "mcp_ids", None):
            mcp_ids = list(draft.mcp_ids)
        if draft.threshold_ids:
            threshold_ids = list(draft.threshold_ids)
        if draft.provider_key_ids:
            provider_key_ids = list(draft.provider_key_ids)
        if draft.auth_item_key_ids:
            auth_item_key_ids = list(draft.auth_item_key_ids)
        # auth_item_values draft connection not yet wired; fall through to artifact.
        if getattr(draft, "auth_ids", None):
            auth_ids = list(draft.auth_ids)
        if getattr(draft, "provider_ids", None):
            provider_ids = list(draft.provider_ids)

    return _MergedIds(
        name_ids=name_ids,
        description_ids=description_ids,
        color_ids=color_ids,
        flag_ids=flag_ids,
        department_ids=department_ids,
        logins_ids=logins_ids,
        systems_ids=systems_ids,
        mcp_ids=mcp_ids,
        threshold_ids=threshold_ids,
        provider_key_ids=provider_key_ids,
        auth_item_key_ids=auth_item_key_ids,
        auth_item_value_ids=auth_item_value_ids,
        auth_ids=auth_ids,
        provider_ids=provider_ids,
    )


async def resolve_setting_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    setting_id: UUID | None,
    group_id: UUID,
    draft_id: UUID | None = None,
    user_department_ids: list[UUID] | None = None,
    names_search: str | None = None,
    descriptions_search: str | None = None,
    colors_search: str | None = None,
    flags_search: str | None = None,
    departments_search: str | None = None,
    logins_search: str | None = None,
    systems_search: str | None = None,
    mcp_search: str | None = None,
    thresholds_search: str | None = None,
    provider_keys_search: str | None = None,
    auth_item_keys_search: str | None = None,
    auth_item_values_search: str | None = None,
    names_limit: int | None = None,
    descriptions_limit: int | None = None,
    colors_limit: int | None = None,
    flags_limit: int | None = None,
    departments_limit: int | None = None,
    logins_limit: int | None = None,
    systems_limit: int | None = None,
    mcp_limit: int | None = None,
    thresholds_limit: int | None = None,
    provider_keys_limit: int | None = None,
    auth_item_keys_limit: int | None = None,
    auth_item_values_limit: int | None = None,
    names_selected_only: bool | None = None,
    descriptions_selected_only: bool | None = None,
    colors_selected_only: bool | None = None,
    flags_selected_only: bool | None = None,
    departments_selected_only: bool | None = None,
    logins_selected_only: bool | None = None,
    systems_selected_only: bool | None = None,
    mcp_selected_only: bool | None = None,
    thresholds_selected_only: bool | None = None,
    provider_keys_selected_only: bool | None = None,
    auth_item_keys_selected_only: bool | None = None,
    auth_item_values_selected_only: bool | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve the setting artifact into fully hydrated canonical resources."""

    user_dept_ids = user_department_ids or []

    async def _fetch_artifacts() -> list[Any]:
        if not setting_id:
            return []
        async with pool.acquire() as conn:
            return await get_setting_artifacts(
                conn,
                [setting_id],
                active=None,
                names=True,
                descriptions=True,
                colors=True,
                departments=True,
                flags=True,
                logins=True,
                systems=True,
                mcp=True,
                thresholds=True,
                provider_keys=True,
                auth_item_keys=True,
                auth_item_values=True,
            )

    async def _fetch_drafts() -> list[Any]:
        if not draft_id:
            return []
        async with pool.acquire() as conn:
            return await get_setting_drafts(conn, [draft_id], redis)

    artifacts, drafts = await asyncio.gather(_fetch_artifacts(), _fetch_drafts())
    artifact = artifacts[0] if artifacts else None
    draft = drafts[0] if drafts else None
    merged = _merge_junction_ids(artifact, draft)

    async def _get_names_selected() -> list[Any]:
        return await get_names(pool, merged.name_ids, redis, bypass_cache)

    async def _search_names_suggestions() -> list[Any]:
        if _selected_only(names_selected_only):
            return []
        async with pool.acquire() as conn:
            return await search_names(
                conn,
                redis,
                search=names_search,
                limit_count=_coalesce_limit(names_limit, 20),
                draft_id=group_id,
                exclude_ids=merged.name_ids,
                bypass_cache=bypass_cache,
                setting=True,
            )

    async def _get_descriptions_selected() -> list[Any]:
        return await get_descriptions(pool, merged.description_ids, redis, bypass_cache)

    async def _search_descriptions_suggestions() -> list[Any]:
        if _selected_only(descriptions_selected_only):
            return []
        async with pool.acquire() as conn:
            return await search_descriptions(
                conn,
                redis,
                search=descriptions_search,
                limit_count=_coalesce_limit(descriptions_limit, 20),
                draft_id=group_id,
                exclude_ids=merged.description_ids,
                bypass_cache=bypass_cache,
                setting=True,
            )

    async def _get_colors_selected() -> list[Any]:
        return await get_colors(pool, merged.color_ids, redis, bypass_cache)

    async def _search_colors_suggestions() -> list[Any]:
        if _selected_only(colors_selected_only):
            return []
        async with pool.acquire() as conn:
            # 500 — the per-role Color pickers need the full catalog (~60
            # rows across 10 roles) so each role group has options.
            return await search_colors(
                conn,
                redis,
                search=colors_search,
                limit_count=_coalesce_limit(colors_limit, 500),
                offset_count=0,
                draft_id=group_id,
                suggest_source="recent" if setting_id else "all",
                exclude_ids=merged.color_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_flags_selected() -> list[Any]:
        return await get_flags(pool, merged.flag_ids, redis, bypass_cache)

    async def _search_flags_suggestions() -> list[Any]:
        if _selected_only(flags_selected_only):
            return []
        async with pool.acquire() as conn:
            # limit must be >= total flag catalog size; search_flags orders
            # by name ASC and prefix-heavy types (setting_active) land past
            # the default 50-row cutoff — the SETTING_FLAG_NAMES post-filter
            # only sees rows that made it through the page window.
            return await search_flags(
                conn,
                redis,
                search=flags_search,
                limit_count=_coalesce_limit(flags_limit, 200),
                offset_count=0,
                exclude_ids=merged.flag_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_departments_selected() -> list[Any]:
        return await get_departments(pool, merged.department_ids, redis, bypass_cache)

    async def _search_departments_suggestions() -> list[Any]:
        if _selected_only(departments_selected_only):
            return []
        async with pool.acquire() as conn:
            return await search_departments(
                conn,
                redis,
                search=departments_search,
                limit_count=_coalesce_limit(departments_limit, 20),
                offset_count=0,
                department_ids=user_dept_ids,
                suggest_source="all",
                exclude_ids=merged.department_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_logins_selected() -> list[Any]:
        return await get_logins(pool, merged.logins_ids, redis, bypass_cache)

    async def _search_logins_suggestions() -> list[Any]:
        if _selected_only(logins_selected_only):
            return []
        async with pool.acquire() as conn:
            return await search_logins(
                conn,
                redis,
                search=logins_search,
                limit_count=_coalesce_limit(logins_limit, 20),
                offset_count=0,
                exclude_ids=merged.logins_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_systems_selected() -> list[Any]:
        return await get_systems(pool, merged.systems_ids, redis, bypass_cache)

    async def _search_systems_suggestions() -> list[Any]:
        if _selected_only(systems_selected_only):
            return []
        async with pool.acquire() as conn:
            return await search_systems(
                conn,
                redis,
                search=systems_search,
                limit_count=_coalesce_limit(systems_limit, 20),
                offset_count=0,
                exclude_ids=merged.systems_ids,
                bypass_cache=bypass_cache,
                setting=True,
            )

    async def _get_mcp_selected() -> list[Any]:
        return await get_mcp(pool, merged.mcp_ids, redis, bypass_cache)

    async def _search_mcp_suggestions() -> list[Any]:
        if _selected_only(mcp_selected_only):
            return []
        async with pool.acquire() as conn:
            return await search_mcp(
                conn,
                redis,
                search=mcp_search,
                limit_count=_coalesce_limit(mcp_limit, 20),
                offset_count=0,
                exclude_ids=merged.mcp_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_thresholds_selected() -> list[Any]:
        return await get_thresholds(pool, merged.threshold_ids, redis, bypass_cache)

    async def _search_thresholds_suggestions() -> list[Any]:
        if _selected_only(thresholds_selected_only):
            return []
        async with pool.acquire() as conn:
            # Drop the setting junction filter — per-type slider pickers
            # need the full catalog so rows at other (type, value) combos
            # are reusable across settings without re-creating duplicates.
            return await search_thresholds(
                conn,
                redis,
                search=thresholds_search,
                limit_count=_coalesce_limit(thresholds_limit, 500),
                offset_count=0,
                exclude_ids=merged.threshold_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_provider_keys_selected() -> list[Any]:
        return await get_provider_keys(pool, merged.provider_key_ids, redis, bypass_cache)

    async def _search_provider_keys_suggestions() -> list[Any]:
        if _selected_only(provider_keys_selected_only):
            return []
        async with pool.acquire() as conn:
            return await search_provider_keys(
                conn,
                redis,
                search=provider_keys_search,
                limit_count=_coalesce_limit(provider_keys_limit, 20),
                offset_count=0,
                exclude_ids=merged.provider_key_ids,
                bypass_cache=bypass_cache,
                setting=True,
            )

    async def _get_auth_item_keys_selected() -> list[Any]:
        return await get_auth_item_keys(pool, merged.auth_item_key_ids, redis, bypass_cache)

    async def _search_auth_item_keys_suggestions() -> list[Any]:
        if _selected_only(auth_item_keys_selected_only):
            return []
        async with pool.acquire() as conn:
            return await search_auth_item_keys(
                conn,
                redis,
                search=auth_item_keys_search,
                limit_count=_coalesce_limit(auth_item_keys_limit, 20),
                offset_count=0,
                exclude_ids=merged.auth_item_key_ids,
                bypass_cache=bypass_cache,
                setting=True,
            )

    async def _get_auth_item_values_selected() -> list[Any]:
        return await get_auth_item_values(pool, merged.auth_item_value_ids, redis, bypass_cache)

    async def _search_provider_catalog() -> list[Any]:
        async with pool.acquire() as conn:
            # Don't filter by user_dept_ids: providers are seeded with empty
            # department_ids ({}) so an overlap filter excludes every row.
            # The Setting page already scopes selection via the picker.
            return await search_providers(
                conn,
                redis,
                search=None,
                limit_count=200,
                bypass_cache=bypass_cache,
                provider=True,
            )

    async def _search_key_catalog() -> list[Any]:
        async with pool.acquire() as conn:
            return await search_keys(
                conn,
                redis,
                search=None,
                limit_count=100,
                bypass_cache=bypass_cache,
                provider=True,
            )

    async def _search_item_catalog() -> list[Any]:
        async with pool.acquire() as conn:
            return await search_items(
                conn,
                redis,
                search=None,
                limit_count=100,
                bypass_cache=bypass_cache,
                auth=True,
            )

    async def _search_profile_catalog() -> list[Any]:
        async with pool.acquire() as conn:
            # profiles is a pure catalog consumed by the Logins picker —
            # there is no setting-scoped profile junction.
            return await search_profiles(
                conn,
                redis,
                search=None,
                limit_count=500,
                bypass_cache=bypass_cache,
            )

    async def _search_auth_catalog() -> list[Any]:
        # Resource rows (id, name, slug, protocol, …) used by the picker.
        async with pool.acquire() as conn:
            return await search_auths(
                conn,
                redis,
                search=None,
                limit_count=200,
                bypass_cache=bypass_cache,
            )


    async def _search_icon_catalog() -> list[Any]:
        async with pool.acquire() as conn:
            return await search_icons(
                conn,
                redis,
                search=None,
                limit_count=500,
                bypass_cache=bypass_cache,
            )

    async def _search_agent_catalog() -> list[Any]:
        async with pool.acquire() as conn:
            return await search_agents(
                conn,
                redis,
                search=None,
                limit_count=500,
                department_ids=user_dept_ids,
                bypass_cache=bypass_cache,
            )

    (
        names_selected,
        names_suggestions,
        descriptions_selected,
        descriptions_suggestions,
        colors_selected,
        colors_suggestions,
        flags_selected,
        flags_suggestions,
        departments_selected,
        departments_suggestions,
        logins_selected,
        logins_suggestions,
        systems_selected,
        systems_suggestions,
        mcp_selected,
        mcp_suggestions,
        thresholds_selected,
        thresholds_suggestions,
        provider_keys_selected,
        provider_keys_suggestions,
        auth_item_keys_selected,
        auth_item_keys_suggestions,
        auth_item_values_selected,
        providers_catalog,
        keys_catalog,
        items_catalog,
        profiles_catalog,
        auths_catalog,
        icons_catalog,
        agents_catalog,
    ) = await asyncio.gather(
        _get_names_selected(),
        _search_names_suggestions(),
        _get_descriptions_selected(),
        _search_descriptions_suggestions(),
        _get_colors_selected(),
        _search_colors_suggestions(),
        _get_flags_selected(),
        _search_flags_suggestions(),
        _get_departments_selected(),
        _search_departments_suggestions(),
        _get_logins_selected(),
        _search_logins_suggestions(),
        _get_systems_selected(),
        _search_systems_suggestions(),
        _get_mcp_selected(),
        _search_mcp_suggestions(),
        _get_thresholds_selected(),
        _search_thresholds_suggestions(),
        _get_provider_keys_selected(),
        _search_provider_keys_suggestions(),
        _get_auth_item_keys_selected(),
        _search_auth_item_keys_suggestions(),
        _get_auth_item_values_selected(),
        _search_provider_catalog(),
        _search_key_catalog(),
        _search_item_catalog(),
        _search_profile_catalog(),
        _search_auth_catalog(),
        _search_icon_catalog(),
        _search_agent_catalog(),
    )

    filtered_flags_selected = [
        item
        for item in flags_selected
        if getattr(item, "name", None) in SETTING_FLAG_NAMES
        or getattr(item, "type", None) in SETTING_FLAG_NAMES
    ]
    filtered_flags_suggestions = [
        item
        for item in flags_suggestions
        if getattr(item, "name", None) in SETTING_FLAG_NAMES
        or getattr(item, "type", None) in SETTING_FLAG_NAMES
    ]

    # Build resource_auth_id → list[item_id] using artifact black boxes.
    # auth_items_junction lives on auth_artifact, not auths_resource, so we
    # ask the artifact to walk it for us. `get_auths(items=True, auths=True)`
    # returns each artifact with its `item_ids` (junction-resolved) and
    # `auth_ids` (linked auths_resource ids), letting us key the map by the
    # resource id the picker uses without any inline SQL.
    item_ids_by_auth_resource: dict[UUID, list[UUID]] = {}
    async with pool.acquire() as conn:
        auth_artifact_ids, _ = await search_auth_artifacts(
            conn, limit_count=500,
        )
    if auth_artifact_ids:
        async with pool.acquire() as conn:
            auth_artifacts = await get_auth_artifacts(
                conn, auth_artifact_ids, items=True, auths=True,
            )
        for art in auth_artifacts:
            item_ids = list(getattr(art, "item_ids", None) or [])
            for resource_id in (getattr(art, "auth_ids", None) or []):
                item_ids_by_auth_resource[resource_id] = item_ids

    pending_ids: set[UUID] = set()
    if draft:
        pending_ids.update(draft.pending_name_ids or [])
        pending_ids.update(draft.pending_description_ids or [])
        pending_ids.update(draft.pending_color_ids or [])
        pending_ids.update(draft.pending_flag_ids or [])
        pending_ids.update(draft.pending_department_ids or [])
        pending_ids.update(getattr(draft, "pending_logins_ids", None) or [])
        pending_ids.update(draft.pending_system_ids or [])
        pending_ids.update(getattr(draft, "pending_mcp_ids", None) or [])
        pending_ids.update(draft.pending_threshold_ids or [])
        pending_ids.update(draft.pending_provider_key_ids or [])
        pending_ids.update(draft.pending_auth_item_key_ids or [])

    # Hydrate SVG icons onto each flag (icon_id → icon markup).
    async with pool.acquire() as conn:
        await hydrate_flag_icons(
            list(filtered_flags_selected) + list(filtered_flags_suggestions),
            conn,
            redis,
            bypass_cache,
        )

    return ArtifactContext(
        artifact_id=artifact.id if artifact else None,
        active=artifact.active if artifact else True,
        group_id=group_id,
        resources={
            "names": ResourcePair(selected=names_selected, suggestions=names_suggestions),
            "descriptions": ResourcePair(selected=descriptions_selected, suggestions=descriptions_suggestions),
            "colors": ResourcePair(selected=colors_selected, suggestions=colors_suggestions),
            "flags": ResourcePair(selected=filtered_flags_selected, suggestions=filtered_flags_suggestions),
            "departments": ResourcePair(selected=departments_selected, suggestions=departments_suggestions),
            "logins": ResourcePair(selected=logins_selected, suggestions=logins_suggestions),
            "systems": ResourcePair(selected=systems_selected, suggestions=systems_suggestions),
            "mcp": ResourcePair(selected=mcp_selected, suggestions=mcp_suggestions),
            "thresholds": ResourcePair(selected=thresholds_selected, suggestions=thresholds_suggestions),
            "provider_keys": ResourcePair(selected=provider_keys_selected, suggestions=provider_keys_suggestions),
            "auth_item_keys": ResourcePair(selected=auth_item_keys_selected, suggestions=auth_item_keys_suggestions),
            "auth_item_values": ResourcePair(selected=auth_item_values_selected, suggestions=[]),
        },
        entries={
            "draft_name": draft.name if draft else None,
            "pending_ids": pending_ids,
            "providers": providers_catalog,
            "keys": keys_catalog,
            "items": items_catalog,
            "profiles": profiles_catalog,
            "auths": auths_catalog,
            "icons": icons_catalog,
            "agents": agents_catalog,
            "selected_auth_ids": set(merged.auth_ids or []),
            "selected_provider_ids": set(merged.provider_ids or []),
            "item_ids_by_auth": item_ids_by_auth_resource,
        },
    )
