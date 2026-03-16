"""Resolve setting artifact context — merged junctions + hydrated resources.

Given a setting_id (and optional draft_id), fetches the published artifact
and draft entry, merges junction IDs (draft overrides published), then
hydrates all resources in parallel (selected + suggestions).

Composes existing black-box fetchers — no raw SQL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.types import ArtifactContext, ResourcePair

# Artifact + draft fetchers
from app.tools.artifacts.setting.get import (
    get_settings as get_setting_artifacts,
)
from app.tools.entries.setting_drafts.get import get_setting_drafts

# Resource get fetchers (by known IDs)
from app.tools.resources.auth_item_keys.get import get_auth_item_keys

# Resource search fetchers (bounded, paginated)
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
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names
from app.tools.resources.profiles.get import get_profiles
from app.tools.resources.profiles.search import search_profiles
from app.tools.resources.provider_keys.get import get_provider_keys
from app.tools.resources.provider_keys.search import search_provider_keys
from app.tools.resources.systems.get import get_systems
from app.tools.resources.systems.search import search_systems

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SETTING_FLAG_NAMES = {"setting_active"}


# ---------------------------------------------------------------------------
# resolve_setting_context
# ---------------------------------------------------------------------------


async def resolve_setting_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    setting_id: UUID | None,
    group_id: UUID,
    draft_id: UUID | None = None,
    user_department_ids: list[UUID] | None = None,
    # Search filters
    color_search: str | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve a setting artifact into fully hydrated resources for the GET endpoint.

    Steps:
      1. Fetch artifact + draft in parallel -> merge IDs
      2. Parallel hydrate: get (selected) + search (suggestions) per resource
      3. Assemble ArtifactContext with ResourcePairs
    """
    user_dept_ids = user_department_ids or []

    # Step 1: fetch artifact + draft in parallel

    async def _fetch_artifacts() -> list:
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

    async def _fetch_drafts() -> list:
        if not draft_id:
            return []
        async with pool.acquire() as conn:
            return await get_setting_drafts(conn, [draft_id])

    artifacts, drafts = await asyncio.gather(_fetch_artifacts(), _fetch_drafts())

    artifact = artifacts[0] if artifacts else None
    draft = drafts[0] if drafts else None

    # Merge IDs: start from published, draft overrides if present
    merged = _merge_junction_ids(artifact, draft)
    draft_version = draft.version if draft else None
    active = artifact.active if artifact else True

    # Step 2: parallel hydrate — selected + suggestions for each resource

    async def _get_names() -> list:
        async with pool.acquire() as conn:
            return await get_names(conn, merged.name_ids, redis, bypass_cache)

    async def _search_names() -> list:
        async with pool.acquire() as conn:
            return await search_names(
                conn,
                redis,
                draft_id=group_id,
                exclude_ids=merged.name_ids,
                bypass_cache=bypass_cache,
                setting=True,
            )

    async def _get_descriptions() -> list:
        async with pool.acquire() as conn:
            return await get_descriptions(
                conn, merged.description_ids, redis, bypass_cache
            )

    async def _search_descriptions() -> list:
        async with pool.acquire() as conn:
            return await search_descriptions(
                conn,
                redis,
                draft_id=group_id,
                exclude_ids=merged.description_ids,
                bypass_cache=bypass_cache,
                setting=True,
            )

    async def _get_colors() -> list:
        async with pool.acquire() as conn:
            return await get_colors(conn, merged.color_ids, redis, bypass_cache)

    async def _search_colors() -> list:
        async with pool.acquire() as conn:
            return await search_colors(
                conn,
                redis,
                search=color_search,
                limit_count=20,
                offset_count=0,
                draft_id=group_id,
                suggest_source="recent" if setting_id else "all",
                exclude_ids=merged.color_ids,
                bypass_cache=bypass_cache,
                setting=True,
            )

    async def _get_flags() -> list:
        async with pool.acquire() as conn:
            return await get_flags(conn, merged.flag_ids, redis, bypass_cache)

    async def _search_flags() -> list:
        async with pool.acquire() as conn:
            return await search_flags(
                conn,
                redis,
                search=None,
                limit_count=50,
                offset_count=0,
                exclude_ids=merged.flag_ids,
                bypass_cache=bypass_cache,
                setting=True,
            )

    async def _get_departments() -> list:
        async with pool.acquire() as conn:
            return await get_departments(
                conn, merged.department_ids, redis, bypass_cache
            )

    async def _search_departments() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                department_ids=user_dept_ids,
                suggest_source="all",
                exclude_ids=merged.department_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_profiles() -> list:
        async with pool.acquire() as conn:
            return await get_profiles(conn, merged.profile_ids, redis, bypass_cache)

    async def _search_profiles() -> list:
        async with pool.acquire() as conn:
            return await search_profiles(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=merged.profile_ids,
                bypass_cache=bypass_cache,
                setting=True,
            )

    async def _get_auths() -> list:
        async with pool.acquire() as conn:
            return await get_auths(conn, merged.auth_ids, redis, bypass_cache)

    async def _search_auths() -> list:
        async with pool.acquire() as conn:
            return await search_auths(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=merged.auth_ids,
                bypass_cache=bypass_cache,
                setting=True,
            )

    async def _get_provider_keys() -> list:
        async with pool.acquire() as conn:
            return await get_provider_keys(
                conn, merged.provider_key_ids, redis, bypass_cache
            )

    async def _search_provider_keys() -> list:
        async with pool.acquire() as conn:
            return await search_provider_keys(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=merged.provider_key_ids,
                bypass_cache=bypass_cache,
                setting=True,
            )

    async def _get_auth_item_keys() -> list:
        async with pool.acquire() as conn:
            return await get_auth_item_keys(
                conn, merged.auth_item_key_ids, redis, bypass_cache
            )

    async def _search_auth_item_keys() -> list:
        async with pool.acquire() as conn:
            return await search_auth_item_keys(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=merged.auth_item_key_ids,
                bypass_cache=bypass_cache,
                setting=True,
            )

    async def _get_systems() -> list:
        async with pool.acquire() as conn:
            return await get_systems(conn, merged.systems_ids, redis, bypass_cache)

    async def _search_systems() -> list:
        async with pool.acquire() as conn:
            return await search_systems(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=merged.systems_ids,
                bypass_cache=bypass_cache,
                setting=True,
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
    ) = await asyncio.gather(
        _get_names(),
        _search_names(),
        _get_descriptions(),
        _search_descriptions(),
        _get_colors(),
        _search_colors(),
        _get_flags(),
        _search_flags(),
        _get_departments(),
        _search_departments(),
        _get_profiles(),
        _search_profiles(),
        _get_auths(),
        _search_auths(),
        _get_provider_keys(),
        _search_provider_keys(),
        _get_auth_item_keys(),
        _search_auth_item_keys(),
        _get_systems(),
        _search_systems(),
    )

    # Filter flags to setting-specific types
    flags_suggestions_filtered = [
        f for f in flags_suggestions if getattr(f, "name", None) in SETTING_FLAG_NAMES
    ]

    return ArtifactContext(
        artifact_id=artifact.id if artifact else None,
        active=active,
        group_id=group_id,
        draft_version=draft_version,
        resources={
            "names": ResourcePair(
                selected=names_selected, suggestions=names_suggestions
            ),
            "descriptions": ResourcePair(
                selected=descriptions_selected, suggestions=descriptions_suggestions
            ),
            "colors": ResourcePair(
                selected=colors_selected, suggestions=colors_suggestions
            ),
            "flags": ResourcePair(
                selected=flags_selected, suggestions=flags_suggestions_filtered
            ),
            "departments": ResourcePair(
                selected=departments_selected, suggestions=departments_suggestions
            ),
            "profiles": ResourcePair(
                selected=profiles_selected, suggestions=profiles_suggestions
            ),
            "auths": ResourcePair(
                selected=auths_selected, suggestions=auths_suggestions
            ),
            "provider_keys": ResourcePair(
                selected=provider_keys_selected, suggestions=provider_keys_suggestions
            ),
            "auth_item_keys": ResourcePair(
                selected=auth_item_keys_selected,
                suggestions=auth_item_keys_suggestions,
            ),
            "systems": ResourcePair(
                selected=systems_selected, suggestions=systems_suggestions
            ),
        },
        entries={},
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


@dataclass
class _MergedIds:
    """Merged junction IDs from artifact + draft."""

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


def _merge_junction_ids(artifact, draft) -> _MergedIds:
    """Merge artifact junction IDs with draft overrides.

    NOTE: Draft uses ``agent_ids`` for the systems connection
    (setting_drafts_agents_connection), while the published artifact
    uses ``systems_ids`` (setting_systems_junction). We map accordingly.
    """
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

    # Draft overrides (if present) — ignore profile_ids from draft
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
        # profile_ids intentionally NOT overridden from draft
        if draft.auth_ids:
            auth_ids = list(draft.auth_ids)
        if draft.provider_key_ids:
            provider_key_ids = list(draft.provider_key_ids)
        if draft.auth_item_key_ids:
            auth_item_key_ids = list(draft.auth_item_key_ids)
        # Draft uses agent_ids for systems (setting_drafts_agents_connection)
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


async def _empty() -> list:
    return []
