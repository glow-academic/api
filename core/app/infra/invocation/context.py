"""Resolve invocation context for the canonical test-owned invocation surface."""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.flag_icons import hydrate_flag_icons
from app.infra.types import ArtifactContext, ResourcePair
from app.tools.entries.invocation_drafts.get import get_invocation_drafts
from app.tools.entries.test_invocation.get import get_test_invocations
from app.tools.resources.departments.get import get_departments
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
from app.tools.resources.reasoning_levels.search import search_reasoning_levels
from app.tools.resources.temperature_levels.get import get_temperature_levels
from app.tools.resources.temperature_levels.search import search_temperature_levels
from app.tools.resources.values.get import get_values
from app.tools.resources.values.search import search_values
from app.tools.resources.voices.get import get_voices
from app.tools.resources.voices.search import search_voices

INVOCATION_FLAG_NAMES = {"invocation_active"}


async def resolve_invocation_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    group_id: UUID,
    invocation_id: UUID | None = None,
    draft_id: UUID | None = None,
    user_department_ids: list[UUID] | None = None,
    names_search: str | None = None,
    descriptions_search: str | None = None,
    values_search: str | None = None,
    flags_search: str | None = None,
    departments_search: str | None = None,
    keys_search: str | None = None,
    endpoints_search: str | None = None,
    modalities_search: str | None = None,
    temperature_levels_search: str | None = None,
    pricing_search: str | None = None,
    reasoning_levels_search: str | None = None,
    qualities_search: str | None = None,
    voices_search: str | None = None,
    names_limit: int | None = None,
    descriptions_limit: int | None = None,
    values_limit: int | None = None,
    flags_limit: int | None = None,
    departments_limit: int | None = None,
    keys_limit: int | None = None,
    endpoints_limit: int | None = None,
    modalities_limit: int | None = None,
    temperature_levels_limit: int | None = None,
    pricing_limit: int | None = None,
    reasoning_levels_limit: int | None = None,
    qualities_limit: int | None = None,
    voices_limit: int | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve invocation into hydrated selected and suggested resources.

    Invocation is owned by the test surface. A test invocation entry provides the
    default operational config, and an invocation draft overlays that state when
    the user customizes the invocation.
    """

    user_dept_ids = user_department_ids or []

    async def _get_base_invocation():
        if invocation_id is None:
            return None
        async with pool.acquire() as conn:
            items = await get_test_invocations(conn, [invocation_id], bypass_mv=bypass_cache)
        return items[0] if items else None

    async def _get_draft():
        if draft_id is None:
            return None
        async with pool.acquire() as conn:
            items = await get_invocation_drafts(conn, [draft_id])
        return items[0] if items else None

    base_invocation, draft = await asyncio.gather(_get_base_invocation(), _get_draft())

    if draft is not None:
        name_ids = list(draft.name_ids or [])
        description_ids = list(draft.description_ids or [])
        flag_ids = list(draft.flag_ids or [])
        department_ids = list(draft.department_ids or [])
        value_ids = [draft.value_id] if draft.value_id else []
        key_ids = list(draft.key_ids or [])
        endpoint_ids = list(draft.endpoint_ids or [])
        temperature_level_ids = list(draft.temperature_level_ids or [])
        pricing_ids = list(draft.pricing_ids or [])
        reasoning_level_ids = list(draft.reasoning_level_ids or [])
        voice_ids = list(draft.voice_ids or [])
    else:
        name_ids = []
        description_ids = []
        flag_ids = []
        department_ids = list(base_invocation.department_ids or []) if base_invocation else []
        value_ids = []
        key_ids = []
        endpoint_ids = []
        temperature_level_ids = (
            [base_invocation.temperature_level_id]
            if base_invocation and base_invocation.temperature_level_id
            else []
        )
        pricing_ids = []
        reasoning_level_ids = (
            [base_invocation.reasoning_level_id]
            if base_invocation and base_invocation.reasoning_level_id
            else []
        )
        voice_ids = (
            [base_invocation.voice_id]
            if base_invocation and base_invocation.voice_id
            else []
        )

    modality_ids = list(base_invocation.modality_ids or []) if base_invocation else []
    quality_ids = (
        [base_invocation.quality_id]
        if base_invocation and base_invocation.quality_id
        else []
    )

    async def _run(getter, ids: list[UUID], searcher, *, search: str | None, limit: int | None, kwargs: dict | None = None):
        kwargs = kwargs or {}

        async def _get():
            async with pool.acquire() as conn:
                return await getter(conn, ids, redis, bypass_cache)

        async def _search():
            async with pool.acquire() as conn:
                return await searcher(
                    conn,
                    redis,
                    search=search,
                    limit_count=limit or 20,
                    offset_count=0,
                    exclude_ids=ids,
                    bypass_cache=bypass_cache,
                    **kwargs,
                )

        return await asyncio.gather(_get(), _search())

    (
        (names_selected, names_suggestions),
        (descriptions_selected, descriptions_suggestions),
        (flags_selected, flags_suggestions),
        (departments_selected, departments_suggestions),
        (values_selected, values_suggestions),
        (keys_selected, keys_suggestions),
        (endpoints_selected, endpoints_suggestions),
        (modalities_selected, modalities_suggestions),
        (temperature_levels_selected, temperature_levels_suggestions),
        (pricing_selected, pricing_suggestions),
        (reasoning_levels_selected, reasoning_levels_suggestions),
        (qualities_selected, qualities_suggestions),
        (voices_selected, voices_suggestions),
    ) = await asyncio.gather(
        _run(
            get_names,
            name_ids,
            search_names,
            search=names_search,
            limit=names_limit,
            kwargs={"draft_id": draft_id},
        ),
        _run(
            get_descriptions,
            description_ids,
            search_descriptions,
            search=descriptions_search,
            limit=descriptions_limit,
            kwargs={"draft_id": draft_id},
        ),
        _run(
            get_flags,
            flag_ids,
            search_flags,
            search=flags_search,
            limit=flags_limit or 100,
            kwargs={"flag_type": "invocation_active"},
        ),
        _run(
            get_departments,
            department_ids,
            search_departments,
            search=departments_search,
            limit=departments_limit,
            kwargs={
                "draft_id": draft_id,
                "department_ids": user_dept_ids,
                "suggest_source": "recent",
            },
        ),
        _run(
            get_values,
            value_ids,
            search_values,
            search=values_search,
            limit=values_limit,
        ),
        _run(
            get_keys,
            key_ids,
            search_keys,
            search=keys_search,
            limit=keys_limit,
        ),
        _run(
            get_endpoints,
            endpoint_ids,
            search_endpoints,
            search=endpoints_search,
            limit=endpoints_limit,
        ),
        _run(
            get_modalities,
            modality_ids,
            search_modalities,
            search=modalities_search,
            limit=modalities_limit,
        ),
        _run(
            get_temperature_levels,
            temperature_level_ids,
            search_temperature_levels,
            search=temperature_levels_search,
            limit=temperature_levels_limit,
        ),
        _run(
            get_pricing,
            pricing_ids,
            search_pricing,
            search=pricing_search,
            limit=pricing_limit,
        ),
        _run(
            get_reasoning_levels,
            reasoning_level_ids,
            search_reasoning_levels,
            search=reasoning_levels_search,
            limit=reasoning_levels_limit,
        ),
        _run(
            get_qualities,
            quality_ids,
            search_qualities,
            search=qualities_search,
            limit=qualities_limit,
        ),
        _run(
            get_voices,
            voice_ids,
            search_voices,
            search=voices_search,
            limit=voices_limit,
            kwargs={"draft_id": draft_id},
        ),
    )

    flags_suggestions = [
        item for item in flags_suggestions if getattr(item, "name", None) in INVOCATION_FLAG_NAMES
    ]

    pending_ids: set[UUID] = set()
    if draft is not None:
        pending_ids.update(draft.pending_name_ids or [])
        pending_ids.update(draft.pending_description_ids or [])
        pending_ids.update(draft.pending_flag_ids or [])
        pending_ids.update(draft.pending_department_ids or [])
        pending_ids.update(draft.pending_key_ids or [])
        pending_ids.update(draft.pending_endpoint_ids or [])
        pending_ids.update(draft.pending_value_ids or [])
        pending_ids.update(draft.pending_temperature_level_ids or [])
        pending_ids.update(draft.pending_pricing_ids or [])
        pending_ids.update(draft.pending_reasoning_level_ids or [])
        pending_ids.update(draft.pending_voice_ids or [])

    # Hydrate SVG icons onto each flag (icon_id → icon markup).
    async with pool.acquire() as conn:
        await hydrate_flag_icons(
            list(flags_selected) + list(flags_suggestions), conn, redis, bypass_cache
        )

    return ArtifactContext(
        artifact_id=invocation_id,
        active=True,
        group_id=group_id,
        resources={
            "names": ResourcePair(selected=names_selected, suggestions=names_suggestions),
            "descriptions": ResourcePair(selected=descriptions_selected, suggestions=descriptions_suggestions),
            "values": ResourcePair(selected=values_selected, suggestions=values_suggestions),
            "flags": ResourcePair(selected=flags_selected, suggestions=flags_suggestions),
            "departments": ResourcePair(selected=departments_selected, suggestions=departments_suggestions),
            "keys": ResourcePair(selected=keys_selected, suggestions=keys_suggestions),
            "endpoints": ResourcePair(selected=endpoints_selected, suggestions=endpoints_suggestions),
            "modalities": ResourcePair(selected=modalities_selected, suggestions=modalities_suggestions),
            "temperature_levels": ResourcePair(
                selected=temperature_levels_selected,
                suggestions=temperature_levels_suggestions,
            ),
            "pricing": ResourcePair(selected=pricing_selected, suggestions=pricing_suggestions),
            "reasoning_levels": ResourcePair(
                selected=reasoning_levels_selected,
                suggestions=reasoning_levels_suggestions,
            ),
            "qualities": ResourcePair(selected=qualities_selected, suggestions=qualities_suggestions),
            "voices": ResourcePair(selected=voices_selected, suggestions=voices_suggestions),
        },
        entries={
            "draft_name": draft.name if draft else None,
            "pending_ids": pending_ids,
            "invocation_exists": base_invocation is not None or draft is not None,
        },
    )
