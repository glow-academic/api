"""Resolve invocation context — draft-only + hydrated resources.

Given a group_id (and optional draft_id), fetches the draft entry and
hydrates all resources in parallel (selected + suggestions).

Invocation is entry-based (no artifact table) and draft-only:
if a draft exists, use its IDs; otherwise all selected lists are empty.

Composes existing black-box fetchers — no raw SQL.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.types import ArtifactContext, ResourcePair

# Draft fetcher
from app.tools.entries.invocation_drafts.get import get_invocation_drafts

# Resource get fetchers (by known IDs)
from app.tools.resources.departments.get import get_departments

# Resource search fetchers (bounded, paginated)
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.endpoints.get import get_endpoints
from app.tools.resources.endpoints.search import search_endpoints
from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.search import search_flags
from app.tools.resources.keys.get import get_keys
from app.tools.resources.keys.search import search_keys
from app.tools.resources.modalities.get import get_modalities
from app.tools.resources.modalities.search import search_modalities
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names
from app.tools.resources.pricing.get import get_pricing
from app.tools.resources.pricing.search import search_pricing
from app.tools.resources.qualities.get import get_qualities
from app.tools.resources.qualities.search import search_qualities
from app.tools.resources.reasoning_levels.get import get_reasoning_levels
from app.tools.resources.reasoning_levels.search import (
    search_reasoning_levels,
)
from app.tools.resources.temperature_levels.get import get_temperature_levels
from app.tools.resources.temperature_levels.search import (
    search_temperature_levels,
)
from app.tools.resources.values.get import get_values
from app.tools.resources.values.search import search_values
from app.tools.resources.voices.get import get_voices
from app.tools.resources.voices.search import search_voices

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INVOCATION_FLAG_NAMES = {"invocation_active"}


# ---------------------------------------------------------------------------
# resolve_invocation_context
# ---------------------------------------------------------------------------


async def resolve_invocation_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    group_id: UUID,
    draft_id: UUID | None = None,
    user_department_ids: list[UUID] | None = None,
    # Search filters
    descriptions_search: str | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve an invocation into fully hydrated resources for the GET endpoint.

    Draft-only pattern:
      1. Fetch draft (if draft_id provided)
      2. Extract IDs from draft — if no draft, all ID lists are empty
      3. Parallel hydrate: get (selected) + search (suggestions) per resource
      4. Assemble ArtifactContext with ResourcePairs
    """
    user_dept_ids = user_department_ids or []

    # Step 1: fetch draft
    async with pool.acquire() as conn:
        drafts = await get_invocation_drafts(conn, [draft_id]) if draft_id else []
    draft = drafts[0] if drafts else None
    draft_version = draft.version if draft else None

    # Step 2: extract IDs from draft (draft-only — no artifact merge)
    name_ids = list(draft.name_ids or []) if draft else []
    description_ids = list(draft.description_ids or []) if draft else []
    flag_ids = list(draft.flag_ids or []) if draft else []
    department_ids = list(draft.department_ids or []) if draft else []
    value_ids = list(draft.value_ids or []) if draft else []
    key_ids = list(draft.key_ids or []) if draft else []
    endpoint_ids = list(draft.endpoint_ids or []) if draft else []
    modality_ids: list[UUID] = []  # no draft connection table for modalities
    temperature_level_ids = list(draft.temperature_level_ids or []) if draft else []
    pricing_ids = list(draft.pricing_ids or []) if draft else []
    reasoning_level_ids = list(draft.reasoning_level_ids or []) if draft else []
    quality_ids: list[UUID] = []  # no draft connection table for qualities
    voice_ids = list(draft.voice_ids or []) if draft else []

    # Step 3: parallel hydrate — selected + suggestions for each resource

    async def _get_names() -> list:
        async with pool.acquire() as conn:
            return await get_names(conn, name_ids, redis, bypass_cache)

    async def _search_names() -> list:
        async with pool.acquire() as conn:
            return await search_names(
                conn,
                redis,
                draft_id=group_id,
                exclude_ids=name_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_descriptions() -> list:
        async with pool.acquire() as conn:
            return await get_descriptions(conn, description_ids, redis, bypass_cache)

    async def _search_descriptions() -> list:
        async with pool.acquire() as conn:
            return await search_descriptions(
                conn,
                redis,
                search=descriptions_search,
                draft_id=group_id,
                exclude_ids=description_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_flags() -> list:
        async with pool.acquire() as conn:
            return await get_flags(conn, flag_ids, redis, bypass_cache)

    async def _search_flags() -> list:
        async with pool.acquire() as conn:
            return await search_flags(
                conn,
                redis,
                search=None,
                limit_count=50,
                offset_count=0,
                exclude_ids=flag_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_departments() -> list:
        async with pool.acquire() as conn:
            return await get_departments(conn, department_ids, redis, bypass_cache)

    async def _search_departments() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                department_ids=user_dept_ids,
                suggest_source="recent",
                exclude_ids=department_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_values() -> list:
        async with pool.acquire() as conn:
            return await get_values(conn, value_ids, redis, bypass_cache)

    async def _search_values() -> list:
        async with pool.acquire() as conn:
            return await search_values(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=value_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_keys() -> list:
        async with pool.acquire() as conn:
            return await get_keys(conn, key_ids, redis, bypass_cache)

    async def _search_keys() -> list:
        async with pool.acquire() as conn:
            return await search_keys(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=key_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_endpoints() -> list:
        async with pool.acquire() as conn:
            return await get_endpoints(conn, endpoint_ids, redis, bypass_cache)

    async def _search_endpoints() -> list:
        async with pool.acquire() as conn:
            return await search_endpoints(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=endpoint_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_modalities() -> list:
        async with pool.acquire() as conn:
            return await get_modalities(conn, modality_ids, redis, bypass_cache)

    async def _search_modalities() -> list:
        async with pool.acquire() as conn:
            return await search_modalities(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=modality_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_temperature_levels() -> list:
        async with pool.acquire() as conn:
            return await get_temperature_levels(
                conn, temperature_level_ids, redis, bypass_cache
            )

    async def _search_temperature_levels() -> list:
        async with pool.acquire() as conn:
            return await search_temperature_levels(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=temperature_level_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_pricing() -> list:
        async with pool.acquire() as conn:
            return await get_pricing(conn, pricing_ids, redis, bypass_cache)

    async def _search_pricing() -> list:
        async with pool.acquire() as conn:
            return await search_pricing(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=pricing_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_reasoning_levels() -> list:
        async with pool.acquire() as conn:
            return await get_reasoning_levels(
                conn, reasoning_level_ids, redis, bypass_cache
            )

    async def _search_reasoning_levels() -> list:
        async with pool.acquire() as conn:
            return await search_reasoning_levels(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=reasoning_level_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_qualities() -> list:
        async with pool.acquire() as conn:
            return await get_qualities(conn, quality_ids, redis, bypass_cache)

    async def _search_qualities() -> list:
        async with pool.acquire() as conn:
            return await search_qualities(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=quality_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_voices() -> list:
        async with pool.acquire() as conn:
            return await get_voices(conn, voice_ids, redis, bypass_cache)

    async def _search_voices() -> list:
        async with pool.acquire() as conn:
            return await search_voices(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=voice_ids,
                bypass_cache=bypass_cache,
            )

    (
        names_selected,
        names_suggestions,
        descriptions_selected,
        descriptions_suggestions,
        flags_selected,
        flags_suggestions,
        departments_selected,
        departments_suggestions,
        values_selected,
        values_suggestions,
        keys_selected,
        keys_suggestions,
        endpoints_selected,
        endpoints_suggestions,
        modalities_selected,
        modalities_suggestions,
        temperature_levels_selected,
        temperature_levels_suggestions,
        pricing_selected,
        pricing_suggestions,
        reasoning_levels_selected,
        reasoning_levels_suggestions,
        qualities_selected,
        qualities_suggestions,
        voices_selected,
        voices_suggestions,
    ) = await asyncio.gather(
        _get_names(),
        _search_names(),
        _get_descriptions(),
        _search_descriptions(),
        _get_flags(),
        _search_flags(),
        _get_departments(),
        _search_departments(),
        _get_values(),
        _search_values(),
        _get_keys(),
        _search_keys(),
        _get_endpoints(),
        _search_endpoints(),
        _get_modalities(),
        _search_modalities(),
        _get_temperature_levels(),
        _search_temperature_levels(),
        _get_pricing(),
        _search_pricing(),
        _get_reasoning_levels(),
        _search_reasoning_levels(),
        _get_qualities(),
        _search_qualities(),
        _get_voices(),
        _search_voices(),
    )

    # Filter flags to invocation-specific types
    flags_suggestions_filtered = [
        f
        for f in flags_suggestions
        if getattr(f, "name", None) in INVOCATION_FLAG_NAMES
    ]

    return ArtifactContext(
        artifact_id=None,
        active=True,
        group_id=group_id,
        draft_version=draft_version,
        resources={
            "names": ResourcePair(
                selected=names_selected, suggestions=names_suggestions
            ),
            "descriptions": ResourcePair(
                selected=descriptions_selected, suggestions=descriptions_suggestions
            ),
            "flags": ResourcePair(
                selected=flags_selected, suggestions=flags_suggestions_filtered
            ),
            "departments": ResourcePair(
                selected=departments_selected, suggestions=departments_suggestions
            ),
            "values": ResourcePair(
                selected=values_selected, suggestions=values_suggestions
            ),
            "keys": ResourcePair(selected=keys_selected, suggestions=keys_suggestions),
            "endpoints": ResourcePair(
                selected=endpoints_selected, suggestions=endpoints_suggestions
            ),
            "modalities": ResourcePair(
                selected=modalities_selected, suggestions=modalities_suggestions
            ),
            "temperature_levels": ResourcePair(
                selected=temperature_levels_selected,
                suggestions=temperature_levels_suggestions,
            ),
            "pricing": ResourcePair(
                selected=pricing_selected, suggestions=pricing_suggestions
            ),
            "reasoning_levels": ResourcePair(
                selected=reasoning_levels_selected,
                suggestions=reasoning_levels_suggestions,
            ),
            "qualities": ResourcePair(
                selected=qualities_selected, suggestions=qualities_suggestions
            ),
            "voices": ResourcePair(
                selected=voices_selected, suggestions=voices_suggestions
            ),
        },
        entries={},
    )
