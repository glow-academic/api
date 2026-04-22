"""Resolve model artifact context — merged junctions + hydrated resources."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.flag_icons import hydrate_flag_icons
from app.infra.types import ArtifactContext, ResourcePair
from app.tools.artifacts.model.get import get_models as get_model_artifacts
from app.tools.entries.model_drafts.get import get_model_drafts
from app.tools.resources.departments.get import get_departments
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
from app.tools.resources.reasoning_levels.search import search_reasoning_levels
from app.tools.resources.temperature_levels.get import get_temperature_levels
from app.tools.resources.temperature_levels.search import search_temperature_levels
from app.tools.resources.values.get import get_values
from app.tools.resources.values.search import search_values
from app.tools.resources.voices.get import get_voices
from app.tools.resources.voices.search import search_voices

MODEL_FLAG_NAMES = {
    "model_active",
    "model_modalities_enabled",
    "model_temperature_enabled",
    "model_pricing_enabled",
    "model_voices_enabled",
    "model_reasoning_levels_enabled",
    "model_qualities_enabled",
}


async def resolve_model_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    model_id: UUID | None,
    group_id: UUID,
    draft_id: UUID | None = None,
    user_department_ids: list[UUID] | None = None,
    names_search: str | None = None,
    descriptions_search: str | None = None,
    values_search: str | None = None,
    providers_search: str | None = None,
    flags_search: str | None = None,
    departments_search: str | None = None,
    modalities_search: str | None = None,
    temperature_levels_search: str | None = None,
    pricing_search: str | None = None,
    reasoning_levels_search: str | None = None,
    qualities_search: str | None = None,
    voices_search: str | None = None,
    names_limit: int | None = None,
    descriptions_limit: int | None = None,
    values_limit: int | None = None,
    providers_limit: int | None = None,
    flags_limit: int | None = None,
    departments_limit: int | None = None,
    modalities_limit: int | None = None,
    temperature_levels_limit: int | None = None,
    pricing_limit: int | None = None,
    reasoning_levels_limit: int | None = None,
    qualities_limit: int | None = None,
    voices_limit: int | None = None,
    names_selected_only: bool | None = None,
    descriptions_selected_only: bool | None = None,
    values_selected_only: bool | None = None,
    providers_selected_only: bool | None = None,
    flags_selected_only: bool | None = None,
    departments_selected_only: bool | None = None,
    modalities_selected_only: bool | None = None,
    temperature_levels_selected_only: bool | None = None,
    pricing_selected_only: bool | None = None,
    reasoning_levels_selected_only: bool | None = None,
    qualities_selected_only: bool | None = None,
    voices_selected_only: bool | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve a model artifact into hydrated selected + suggested resources."""

    user_dept_ids = user_department_ids or []

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
    merged = _merge_junction_ids(artifact, draft)
    active = artifact.active if artifact else True

    async def _get_names() -> list:
        async with pool.acquire() as conn:
            return await get_names(conn, merged.name_ids, redis, bypass_cache)

    async def _search_names() -> list:
        if names_selected_only:
            return []
        async with pool.acquire() as conn:
            return await search_names(
                conn,
                redis,
                search=names_search,
                limit_count=names_limit or 20,
                draft_id=group_id,
                exclude_ids=merged.name_ids,
                bypass_cache=bypass_cache,
                model=True,
            )

    async def _get_descriptions() -> list:
        async with pool.acquire() as conn:
            return await get_descriptions(conn, merged.description_ids, redis, bypass_cache)

    async def _search_descriptions() -> list:
        if descriptions_selected_only:
            return []
        async with pool.acquire() as conn:
            return await search_descriptions(
                conn,
                redis,
                search=descriptions_search,
                limit_count=descriptions_limit or 20,
                draft_id=group_id,
                exclude_ids=merged.description_ids,
                bypass_cache=bypass_cache,
                model=True,
            )

    async def _get_flags() -> list:
        async with pool.acquire() as conn:
            return await get_flags(conn, merged.flag_ids, redis, bypass_cache)

    async def _search_flags() -> list:
        if flags_selected_only:
            return []
        async with pool.acquire() as conn:
            return await search_flags(
                conn,
                redis,
                search=flags_search,
                limit_count=flags_limit or 50,
                offset_count=0,
                exclude_ids=merged.flag_ids,
                bypass_cache=bypass_cache,
                model=True,
            )

    async def _get_departments() -> list:
        async with pool.acquire() as conn:
            return await get_departments(conn, merged.department_ids, redis, bypass_cache)

    async def _search_departments() -> list:
        if departments_selected_only:
            return []
        async with pool.acquire() as conn:
            return await search_departments(
                conn,
                redis,
                search=departments_search,
                limit_count=departments_limit or 20,
                offset_count=0,
                department_ids=user_dept_ids,
                suggest_source="all" if model_id is None else "recent",
                exclude_ids=merged.department_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_values() -> list:
        if not merged.value_id:
            return []
        async with pool.acquire() as conn:
            return await get_values(conn, [merged.value_id], redis, bypass_cache)

    async def _search_values() -> list:
        if values_selected_only:
            return []
        async with pool.acquire() as conn:
            return await search_values(
                conn,
                redis,
                search=values_search,
                limit_count=values_limit or 20,
                suggest_source="recent",
                exclude_ids=[merged.value_id] if merged.value_id else [],
                bypass_cache=bypass_cache,
                model=True,
            )

    async def _get_providers() -> list:
        if not merged.provider_id:
            return []
        async with pool.acquire() as conn:
            return await get_providers(conn, [merged.provider_id], redis, bypass_cache=bypass_cache)

    async def _search_providers() -> list:
        if providers_selected_only:
            return []
        async with pool.acquire() as conn:
            return await search_providers(
                conn,
                redis,
                search=providers_search,
                limit_count=providers_limit or 20,
                offset_count=0,
                exclude_ids=[merged.provider_id] if merged.provider_id else [],
                department_ids=user_dept_ids,
                bypass_cache=bypass_cache,
                model=True,
            )

    async def _get_modalities() -> list:
        async with pool.acquire() as conn:
            return await get_modalities(conn, merged.modality_ids, redis, bypass_cache)

    async def _search_modalities() -> list:
        if modalities_selected_only:
            return []
        async with pool.acquire() as conn:
            return await search_modalities(
                conn,
                redis,
                search=modalities_search,
                limit_count=modalities_limit or 20,
                offset_count=0,
                exclude_ids=merged.modality_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_temperature_levels() -> list:
        async with pool.acquire() as conn:
            return await get_temperature_levels(
                conn,
                merged.temperature_level_ids,
                redis,
                bypass_cache,
            )

    async def _search_temperature_levels() -> list:
        if temperature_levels_selected_only:
            return []
        async with pool.acquire() as conn:
            return await search_temperature_levels(
                conn,
                redis,
                search=temperature_levels_search,
                limit_count=temperature_levels_limit or 20,
                offset_count=0,
                exclude_ids=merged.temperature_level_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_pricing() -> list:
        async with pool.acquire() as conn:
            return await get_pricing(conn, merged.pricing_ids, redis, bypass_cache)

    async def _search_pricing() -> list:
        if pricing_selected_only:
            return []
        async with pool.acquire() as conn:
            return await search_pricing(
                conn,
                redis,
                search=pricing_search,
                limit_count=pricing_limit or 20,
                offset_count=0,
                exclude_ids=merged.pricing_ids,
                bypass_cache=bypass_cache,
                model=True,
            )

    async def _get_reasoning_levels() -> list:
        async with pool.acquire() as conn:
            return await get_reasoning_levels(conn, merged.reasoning_level_ids, redis, bypass_cache)

    async def _search_reasoning_levels() -> list:
        if reasoning_levels_selected_only:
            return []
        async with pool.acquire() as conn:
            return await search_reasoning_levels(
                conn,
                redis,
                search=reasoning_levels_search,
                limit_count=reasoning_levels_limit or 20,
                offset_count=0,
                exclude_ids=merged.reasoning_level_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_qualities() -> list:
        async with pool.acquire() as conn:
            return await get_qualities(conn, merged.quality_ids, redis, bypass_cache)

    async def _search_qualities() -> list:
        if qualities_selected_only:
            return []
        async with pool.acquire() as conn:
            return await search_qualities(
                conn,
                redis,
                search=qualities_search,
                limit_count=qualities_limit or 20,
                offset_count=0,
                exclude_ids=merged.quality_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_voices() -> list:
        async with pool.acquire() as conn:
            return await get_voices(conn, merged.voice_ids, redis, bypass_cache)

    async def _search_voices() -> list:
        if voices_selected_only:
            return []
        async with pool.acquire() as conn:
            return await search_voices(
                conn,
                redis,
                search=voices_search,
                limit_count=voices_limit or 20,
                offset_count=0,
                exclude_ids=merged.voice_ids,
                bypass_cache=bypass_cache,
                model=True,
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

    flags_suggestions_filtered = [
        item for item in flags_suggestions if getattr(item, "name", None) in MODEL_FLAG_NAMES
    ]

    pending_ids: set[UUID] = set()
    if draft:
        pending_ids.update(draft.pending_name_ids or [])
        pending_ids.update(draft.pending_description_ids or [])
        pending_ids.update(draft.pending_flag_ids or [])
        pending_ids.update(draft.pending_department_ids or [])
        pending_ids.update(draft.pending_value_ids or [])
        pending_ids.update(draft.pending_provider_ids or [])
        pending_ids.update(draft.pending_modality_ids or [])
        pending_ids.update(draft.pending_temperature_level_ids or [])
        pending_ids.update(draft.pending_pricing_ids or [])
        pending_ids.update(draft.pending_reasoning_level_ids or [])
        pending_ids.update(draft.pending_quality_ids or [])
        pending_ids.update(draft.pending_voice_ids or [])

    # Hydrate SVG icons onto each flag (icon_id → icon markup).
    async with pool.acquire() as conn:
        await hydrate_flag_icons(
            list(flags_selected) + list(flags_suggestions_filtered), conn, redis, bypass_cache
        )

    return ArtifactContext(
        artifact_id=artifact.id if artifact else None,
        active=active,
        group_id=group_id,
        resources={
            "names": ResourcePair(selected=names_selected, suggestions=names_suggestions),
            "descriptions": ResourcePair(selected=descriptions_selected, suggestions=descriptions_suggestions),
            "flags": ResourcePair(selected=flags_selected, suggestions=flags_suggestions_filtered),
            "departments": ResourcePair(selected=departments_selected, suggestions=departments_suggestions),
            "values": ResourcePair(selected=values_selected, suggestions=values_suggestions),
            "providers": ResourcePair(selected=providers_selected, suggestions=providers_suggestions),
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
        entries={"pending_ids": pending_ids},
    )


@dataclass
class _MergedIds:
    name_ids: list[UUID]
    description_ids: list[UUID]
    flag_ids: list[UUID]
    department_ids: list[UUID]
    value_id: UUID | None
    provider_id: UUID | None
    modality_ids: list[UUID]
    temperature_level_ids: list[UUID]
    pricing_ids: list[UUID]
    reasoning_level_ids: list[UUID]
    quality_ids: list[UUID]
    voice_ids: list[UUID]


def _merge_junction_ids(artifact, draft) -> _MergedIds:
    """Merge published artifact junction IDs with draft overrides."""

    name_ids = list(artifact.name_ids or []) if artifact else []
    description_ids = list(artifact.description_ids or []) if artifact else []
    flag_ids = list(artifact.flag_ids or []) if artifact else []
    department_ids = list(artifact.department_ids or []) if artifact else []
    value_id = artifact.value_id if artifact else None
    provider_id = artifact.provider_id if artifact else None
    modality_ids = list(artifact.modality_ids or []) if artifact else []
    temperature_level_ids = list(artifact.temperature_level_ids or []) if artifact else []
    pricing_ids = list(artifact.pricing_ids or []) if artifact else []
    reasoning_level_ids = list(artifact.reasoning_level_ids or []) if artifact else []
    quality_ids = list(artifact.quality_ids or []) if artifact else []
    voice_ids = list(artifact.voice_ids or []) if artifact else []

    if draft:
        if draft.name_ids:
            name_ids = list(draft.name_ids)
        if draft.description_ids:
            description_ids = list(draft.description_ids)
        if draft.flag_ids:
            flag_ids = list(draft.flag_ids)
        if draft.department_ids:
            department_ids = list(draft.department_ids)
        if draft.value_id is not None:
            value_id = draft.value_id
        if draft.provider_ids:
            provider_id = draft.provider_ids[0] if draft.provider_ids else None
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
        value_id=value_id,
        provider_id=provider_id,
        modality_ids=modality_ids,
        temperature_level_ids=temperature_level_ids,
        pricing_ids=pricing_ids,
        reasoning_level_ids=reasoning_level_ids,
        quality_ids=quality_ids,
        voice_ids=voice_ids,
    )
