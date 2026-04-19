"""Resolve setting artifact context — merged junctions + hydrated resources."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.types import ArtifactContext, ResourcePair
from app.tools.artifacts.setting.get import get_settings as get_setting_artifacts
from app.tools.entries.setting_drafts.get import get_setting_drafts
from app.tools.resources.auth_item_keys.get import get_auth_item_keys
from app.tools.resources.auth_item_keys.search import search_auth_item_keys
from app.tools.resources.auths.get import get_auths
from app.tools.resources.auths.search import search_auths
from app.tools.resources.colors.get import get_colors
from app.tools.resources.colors.search import search_colors
from app.tools.resources.departments.get import get_departments
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.search import search_flags
from app.tools.resources.keys.search import search_keys
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names
from app.tools.resources.profiles.get import get_profiles
from app.tools.resources.profiles.search import search_profiles
from app.tools.resources.provider_keys.get import get_provider_keys
from app.tools.resources.provider_keys.search import search_provider_keys
from app.tools.resources.providers.search import search_providers
from app.tools.resources.systems.get import get_systems
from app.tools.resources.systems.search import search_systems

SETTING_FLAG_NAMES = {"setting_active"}


@dataclass
class _MergedIds:
    name_ids: list[UUID]
    description_ids: list[UUID]
    color_ids: list[UUID]
    flag_ids: list[UUID]
    department_ids: list[UUID]
    profile_ids: list[UUID]
    auth_ids: list[UUID]
    provider_key_ids: list[UUID]
    auth_item_key_ids: list[UUID]
    systems_ids: list[UUID]


def _coalesce_limit(value: int | None, fallback: int) -> int:
    return value if value and value > 0 else fallback


def _selected_only(value: bool | None) -> bool:
    return bool(value)


def _merge_junction_ids(
    artifact: Any,
    draft: Any,
    *,
    owner_profile_id: UUID | None,
) -> _MergedIds:
    """Merge artifact junction IDs with draft overrides.

    Drafts reuse ``setting_drafts_profiles_connection`` both for draft ownership and
    for editable setting profile links. The owner's profile must therefore be
    excluded from the editable selection surface while still remaining on the
    draft for ownership queries.
    """

    owner_profile = str(owner_profile_id) if owner_profile_id else None

    name_ids = list(artifact.name_ids or []) if artifact else []
    description_ids = list(artifact.description_ids or []) if artifact else []
    color_ids = list(artifact.color_ids or []) if artifact else []
    flag_ids = list(artifact.flag_ids or []) if artifact else []
    department_ids = list(artifact.department_ids or []) if artifact else []
    profile_ids = list(artifact.profile_ids or []) if artifact else []
    auth_ids = list(artifact.auth_ids or []) if artifact else []
    provider_key_ids = list(artifact.provider_key_ids or []) if artifact else []
    auth_item_key_ids = list(artifact.auth_item_keys_ids or []) if artifact else []
    systems_ids = list(artifact.systems_ids or []) if artifact else []

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
        if draft.profile_ids:
            profile_ids = [
                profile_id
                for profile_id in draft.profile_ids
                if owner_profile is None or str(profile_id) != owner_profile
            ]
        if draft.auth_ids:
            auth_ids = list(draft.auth_ids)
        if draft.provider_key_ids:
            provider_key_ids = list(draft.provider_key_ids)
        if draft.auth_item_key_ids:
            auth_item_key_ids = list(draft.auth_item_key_ids)
        if draft.agent_ids:
            systems_ids = list(draft.agent_ids)

    return _MergedIds(
        name_ids=name_ids,
        description_ids=description_ids,
        color_ids=color_ids,
        flag_ids=flag_ids,
        department_ids=department_ids,
        profile_ids=profile_ids,
        auth_ids=auth_ids,
        provider_key_ids=provider_key_ids,
        auth_item_key_ids=auth_item_key_ids,
        systems_ids=systems_ids,
    )


async def resolve_setting_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    setting_id: UUID | None,
    group_id: UUID,
    draft_id: UUID | None = None,
    user_department_ids: list[UUID] | None = None,
    owner_profile_id: UUID | None = None,
    names_search: str | None = None,
    descriptions_search: str | None = None,
    colors_search: str | None = None,
    flags_search: str | None = None,
    departments_search: str | None = None,
    profiles_search: str | None = None,
    auths_search: str | None = None,
    provider_keys_search: str | None = None,
    auth_item_keys_search: str | None = None,
    systems_search: str | None = None,
    names_limit: int | None = None,
    descriptions_limit: int | None = None,
    colors_limit: int | None = None,
    flags_limit: int | None = None,
    departments_limit: int | None = None,
    profiles_limit: int | None = None,
    auths_limit: int | None = None,
    provider_keys_limit: int | None = None,
    auth_item_keys_limit: int | None = None,
    systems_limit: int | None = None,
    names_selected_only: bool | None = None,
    descriptions_selected_only: bool | None = None,
    colors_selected_only: bool | None = None,
    flags_selected_only: bool | None = None,
    departments_selected_only: bool | None = None,
    profiles_selected_only: bool | None = None,
    auths_selected_only: bool | None = None,
    provider_keys_selected_only: bool | None = None,
    auth_item_keys_selected_only: bool | None = None,
    systems_selected_only: bool | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve the setting artifact into fully hydrated resources."""

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
                profiles=True,
                auths=True,
                provider_keys=True,
                auth_item_keys=True,
                systems=True,
            )

    async def _fetch_drafts() -> list[Any]:
        if not draft_id:
            return []
        async with pool.acquire() as conn:
            return await get_setting_drafts(conn, [draft_id])

    artifacts, drafts = await asyncio.gather(_fetch_artifacts(), _fetch_drafts())
    artifact = artifacts[0] if artifacts else None
    draft = drafts[0] if drafts else None
    merged = _merge_junction_ids(
        artifact,
        draft,
        owner_profile_id=owner_profile_id,
    )

    async def _get_names_selected() -> list[Any]:
        async with pool.acquire() as conn:
            return await get_names(conn, merged.name_ids, redis, bypass_cache)

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
        async with pool.acquire() as conn:
            return await get_descriptions(conn, merged.description_ids, redis, bypass_cache)

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
        async with pool.acquire() as conn:
            return await get_colors(conn, merged.color_ids, redis, bypass_cache)

    async def _search_colors_suggestions() -> list[Any]:
        if _selected_only(colors_selected_only):
            return []
        async with pool.acquire() as conn:
            return await search_colors(
                conn,
                redis,
                search=colors_search,
                limit_count=_coalesce_limit(colors_limit, 20),
                offset_count=0,
                draft_id=group_id,
                suggest_source="recent" if setting_id else "all",
                exclude_ids=merged.color_ids,
                bypass_cache=bypass_cache,
                setting=True,
            )

    async def _get_flags_selected() -> list[Any]:
        async with pool.acquire() as conn:
            return await get_flags(conn, merged.flag_ids, redis, bypass_cache)

    async def _search_flags_suggestions() -> list[Any]:
        if _selected_only(flags_selected_only):
            return []
        async with pool.acquire() as conn:
            return await search_flags(
                conn,
                redis,
                search=flags_search,
                limit_count=_coalesce_limit(flags_limit, 50),
                offset_count=0,
                exclude_ids=merged.flag_ids,
                bypass_cache=bypass_cache,
                setting=True,
            )

    async def _get_departments_selected() -> list[Any]:
        async with pool.acquire() as conn:
            return await get_departments(conn, merged.department_ids, redis, bypass_cache)

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

    async def _get_profiles_selected() -> list[Any]:
        async with pool.acquire() as conn:
            return await get_profiles(conn, merged.profile_ids, redis, bypass_cache)

    async def _search_profiles_suggestions() -> list[Any]:
        if _selected_only(profiles_selected_only):
            return []
        async with pool.acquire() as conn:
            return await search_profiles(
                conn,
                redis,
                search=profiles_search,
                limit_count=_coalesce_limit(profiles_limit, 20),
                offset_count=0,
                exclude_ids=merged.profile_ids,
                bypass_cache=bypass_cache,
                setting=True,
            )

    async def _get_auths_selected() -> list[Any]:
        async with pool.acquire() as conn:
            return await get_auths(conn, merged.auth_ids, redis, bypass_cache)

    async def _search_auths_suggestions() -> list[Any]:
        if _selected_only(auths_selected_only):
            return []
        async with pool.acquire() as conn:
            return await search_auths(
                conn,
                redis,
                search=auths_search,
                limit_count=_coalesce_limit(auths_limit, 20),
                offset_count=0,
                exclude_ids=merged.auth_ids,
                bypass_cache=bypass_cache,
                setting=True,
            )

    async def _get_provider_keys_selected() -> list[Any]:
        async with pool.acquire() as conn:
            return await get_provider_keys(conn, merged.provider_key_ids, redis, bypass_cache)

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
        async with pool.acquire() as conn:
            return await get_auth_item_keys(conn, merged.auth_item_key_ids, redis, bypass_cache)

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

    async def _get_systems_selected() -> list[Any]:
        async with pool.acquire() as conn:
            return await get_systems(conn, merged.systems_ids, redis, bypass_cache)

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

    async def _search_provider_catalog() -> list[Any]:
        async with pool.acquire() as conn:
            return await search_providers(
                conn,
                redis,
                search=None,
                limit_count=100,
                department_ids=user_dept_ids,
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
        profiles_selected,
        profiles_suggestions,
        auths_selected,
        auths_suggestions,
        provider_keys_selected,
        provider_keys_suggestions,
        auth_item_keys_selected,
        auth_item_keys_suggestions,
        systems_selected,
        systems_suggestions,
        providers_catalog,
        keys_catalog,
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
        _get_profiles_selected(),
        _search_profiles_suggestions(),
        _get_auths_selected(),
        _search_auths_suggestions(),
        _get_provider_keys_selected(),
        _search_provider_keys_suggestions(),
        _get_auth_item_keys_selected(),
        _search_auth_item_keys_suggestions(),
        _get_systems_selected(),
        _search_systems_suggestions(),
        _search_provider_catalog(),
        _search_key_catalog(),
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

    pending_ids: set[UUID] = set()
    if draft:
        pending_ids.update(draft.pending_name_ids or [])
        pending_ids.update(draft.pending_description_ids or [])
        pending_ids.update(draft.pending_color_ids or [])
        pending_ids.update(draft.pending_flag_ids or [])
        pending_ids.update(draft.pending_department_ids or [])
        pending_ids.update(
            [
                profile_id
                for profile_id in (draft.pending_profile_ids or [])
                if owner_profile_id is None or profile_id != owner_profile_id
            ]
        )
        pending_ids.update(draft.pending_auth_ids or [])
        pending_ids.update(draft.pending_provider_key_ids or [])
        pending_ids.update(draft.pending_auth_item_key_ids or [])
        pending_ids.update(draft.pending_agent_ids or [])

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
            "profiles": ResourcePair(selected=profiles_selected, suggestions=profiles_suggestions),
            "auths": ResourcePair(selected=auths_selected, suggestions=auths_suggestions),
            "provider_keys": ResourcePair(selected=provider_keys_selected, suggestions=provider_keys_suggestions),
            "auth_item_keys": ResourcePair(selected=auth_item_keys_selected, suggestions=auth_item_keys_suggestions),
            "systems": ResourcePair(selected=systems_selected, suggestions=systems_suggestions),
        },
        entries={
            "pending_ids": pending_ids,
            "providers": providers_catalog,
            "keys": keys_catalog,
        },
    )
