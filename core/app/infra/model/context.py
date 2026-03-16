"""Resolve model artifact context — merged junctions + hydrated resources.

Given a model_id (and optional draft_id), fetches the published artifact
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
from app.tools.artifacts.model.get import (
    get_models as get_model_artifacts,
)
from app.tools.entries.model_drafts.get import get_model_drafts

# Resource get fetchers (by known IDs)
from app.tools.resources.departments.get import get_departments

# Resource search fetchers (bounded, paginated)
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.search import search_flags
from app.tools.resources.modalities.get import get_modalities
from app.tools.resources.modalities.search import search_modalities
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names
from app.tools.resources.pricing.get import get_pricing
from app.tools.resources.pricing.search import search_pricing
from app.tools.resources.providers.get import get_providers
from app.tools.resources.providers.search import search_providers
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

MODEL_FLAG_NAMES = {
    "model_active",
    "model_modalities_enabled",
    "model_temperature_enabled",
    "model_pricing_enabled",
    "model_voices_enabled",
    "model_reasoning_levels_enabled",
    "model_qualities_enabled",
}


# ---------------------------------------------------------------------------
# resolve_model_context
# ---------------------------------------------------------------------------


async def resolve_model_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    model_id: UUID | None,
    group_id: UUID,
    draft_id: UUID | None = None,
    user_department_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve a model artifact into fully hydrated resources for the GET endpoint.

    Steps:
      1. Fetch artifact + draft in parallel -> merge IDs
      2. Parallel hydrate: get (selected) + search (suggestions) per resource
      3. Assemble ArtifactContext with ResourcePairs
    """
    user_dept_ids = user_department_ids or []

    # Step 1: fetch artifact + draft in parallel
    async def _fetch_artifact() -> list:
        if not model_id:
            return []
        async with pool.acquire() as conn:
            return await get_model_artifacts(
                conn,
                [model_id],
                active=None,
                names=True,
                descriptions=True,
                departments=True,
                flags=True,
                values=True,
                providers=True,
                modalities=True,
                temperature_levels=True,
                pricing=True,
                reasoning_levels=True,
                qualities=True,
                voices=True,
            )

    async def _fetch_draft() -> list:
        if not draft_id:
            return []
        async with pool.acquire() as conn:
            return await get_model_drafts(conn, [draft_id])

    artifacts, drafts = await asyncio.gather(_fetch_artifact(), _fetch_draft())

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
                model=True,
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
                model=True,
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
                model=True,
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
                suggest_source="all" if model_id is None else "recent",
                exclude_ids=merged.department_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_values() -> list:
        async with pool.acquire() as conn:
            return await get_values(conn, merged.value_ids, redis, bypass_cache)

    async def _search_values() -> list:
        async with pool.acquire() as conn:
            return await search_values(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=merged.value_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_providers() -> list:
        async with pool.acquire() as conn:
            return await get_providers(
                conn, merged.provider_ids, redis, bypass_cache=bypass_cache
            )

    async def _search_providers() -> list:
        async with pool.acquire() as conn:
            return await search_providers(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=merged.provider_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_modalities() -> list:
        async with pool.acquire() as conn:
            return await get_modalities(conn, merged.modality_ids, redis, bypass_cache)

    async def _search_modalities() -> list:
        async with pool.acquire() as conn:
            return await search_modalities(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=merged.modality_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_temperature_levels() -> list:
        async with pool.acquire() as conn:
            return await get_temperature_levels(
                conn, merged.temperature_level_ids, redis, bypass_cache
            )

    async def _search_temperature_levels() -> list:
        async with pool.acquire() as conn:
            return await search_temperature_levels(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=merged.temperature_level_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_pricing() -> list:
        async with pool.acquire() as conn:
            return await get_pricing(conn, merged.pricing_ids, redis, bypass_cache)

    async def _search_pricing() -> list:
        async with pool.acquire() as conn:
            return await search_pricing(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=merged.pricing_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_reasoning_levels() -> list:
        async with pool.acquire() as conn:
            return await get_reasoning_levels(
                conn, merged.reasoning_level_ids, redis, bypass_cache
            )

    async def _search_reasoning_levels() -> list:
        async with pool.acquire() as conn:
            return await search_reasoning_levels(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=merged.reasoning_level_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_qualities() -> list:
        async with pool.acquire() as conn:
            return await get_qualities(conn, merged.quality_ids, redis, bypass_cache)

    async def _search_qualities() -> list:
        async with pool.acquire() as conn:
            return await search_qualities(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=merged.quality_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_voices() -> list:
        async with pool.acquire() as conn:
            return await get_voices(conn, merged.voice_ids, redis, bypass_cache)

    async def _search_voices() -> list:
        async with pool.acquire() as conn:
            return await search_voices(
                conn,
                redis,
                search=None,
                limit_count=20,
                offset_count=0,
                exclude_ids=merged.voice_ids,
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
        providers_selected,
        providers_suggestions,
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
        _get_providers(),
        _search_providers(),
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

    # Filter flags to model-specific types
    flags_suggestions_filtered = [
        f for f in flags_suggestions if getattr(f, "name", None) in MODEL_FLAG_NAMES
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
            "flags": ResourcePair(
                selected=flags_selected, suggestions=flags_suggestions_filtered
            ),
            "departments": ResourcePair(
                selected=departments_selected, suggestions=departments_suggestions
            ),
            "values": ResourcePair(
                selected=values_selected, suggestions=values_suggestions
            ),
            "providers": ResourcePair(
                selected=providers_selected, suggestions=providers_suggestions
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


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


@dataclass
class _MergedIds:
    """Merged junction IDs from artifact + draft."""

    name_ids: list[UUID]
    description_ids: list[UUID]
    flag_ids: list[UUID]
    department_ids: list[UUID]
    value_ids: list[UUID]
    provider_ids: list[UUID]
    modality_ids: list[UUID]
    temperature_level_ids: list[UUID]
    pricing_ids: list[UUID]
    reasoning_level_ids: list[UUID]
    quality_ids: list[UUID]
    voice_ids: list[UUID]


def _merge_junction_ids(artifact, draft) -> _MergedIds:
    """Merge artifact junction IDs with draft overrides."""
    name_ids = list(artifact.name_ids or []) if artifact else []
    description_ids = list(artifact.description_ids or []) if artifact else []
    flag_ids = list(artifact.flag_ids or []) if artifact else []
    department_ids = list(artifact.department_ids or []) if artifact else []
    value_ids = list(artifact.value_ids or []) if artifact else []
    provider_ids = list(artifact.provider_ids or []) if artifact else []
    modality_ids = list(artifact.modality_ids or []) if artifact else []
    temperature_level_ids = (
        list(artifact.temperature_level_ids or []) if artifact else []
    )
    pricing_ids = list(artifact.pricing_ids or []) if artifact else []
    reasoning_level_ids = list(artifact.reasoning_level_ids or []) if artifact else []
    quality_ids = list(artifact.quality_ids or []) if artifact else []
    voice_ids = list(artifact.voice_ids or []) if artifact else []

    # Draft overrides (if present) — ignore profile_ids from draft
    if draft:
        if draft.name_ids:
            name_ids = list(draft.name_ids)
        if draft.description_ids:
            description_ids = list(draft.description_ids)
        if draft.flag_ids:
            flag_ids = list(draft.flag_ids)
        if draft.department_ids:
            department_ids = list(draft.department_ids)
        if draft.value_ids:
            value_ids = list(draft.value_ids)
        if draft.provider_ids:
            provider_ids = list(draft.provider_ids)
        if draft.modality_ids:
            modality_ids = list(draft.modality_ids)
        if draft.temperature_level_ids:
            temperature_level_ids = list(draft.temperature_level_ids)
        if draft.pricing_ids:
            pricing_ids = list(draft.pricing_ids)
        if draft.reasoning_level_ids:
            reasoning_level_ids = list(draft.reasoning_level_ids)
        if draft.quality_ids:
            quality_ids = list(draft.quality_ids)
        if draft.voice_ids:
            voice_ids = list(draft.voice_ids)

    return _MergedIds(
        name_ids=name_ids,
        description_ids=description_ids,
        flag_ids=flag_ids,
        department_ids=department_ids,
        value_ids=value_ids,
        provider_ids=provider_ids,
        modality_ids=modality_ids,
        temperature_level_ids=temperature_level_ids,
        pricing_ids=pricing_ids,
        reasoning_level_ids=reasoning_level_ids,
        quality_ids=quality_ids,
        voice_ids=voice_ids,
    )


async def _empty() -> list:
    return []
