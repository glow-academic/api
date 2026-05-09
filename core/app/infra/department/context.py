"""Resolve department artifact context — merged junctions + hydrated resources."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.flag_icons import hydrate_flag_icons
from app.infra.types import ArtifactContext, ResourcePair
from app.tools.artifacts.department.get import (
    get_departments as get_department_artifacts,
)
from app.tools.entries.department_drafts.get import get_department_drafts
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names
from app.tools.resources.settings.get import get_settings
from app.tools.resources.settings.search import search_settings

DEPARTMENT_FLAG_NAMES = {"department_active"}


@dataclass
class _MergedIds:
    name_ids: list[UUID]
    description_ids: list[UUID]
    flag_ids: list[UUID]
    setting_ids: list[UUID]


def _merge_junction_ids(artifact: Any, draft: Any) -> _MergedIds:
    name_ids = list(artifact.name_ids or []) if artifact else []
    description_ids = list(artifact.description_ids or []) if artifact else []
    flag_ids = list(artifact.flag_ids or []) if artifact else []
    setting_ids = list(artifact.settings_ids or []) if artifact else []

    if draft:
        if draft.name_ids:
            name_ids = list(draft.name_ids)
        if draft.description_ids:
            description_ids = list(draft.description_ids)
        if draft.flag_ids:
            flag_ids = list(draft.flag_ids)
        if draft.setting_ids:
            setting_ids = list(draft.setting_ids)

    return _MergedIds(
        name_ids=name_ids,
        description_ids=description_ids,
        flag_ids=flag_ids,
        setting_ids=setting_ids,
    )


async def resolve_department_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    department_id: UUID | None,
    group_id: UUID,
    draft_id: UUID | None = None,
    names_search: str | None = None,
    descriptions_search: str | None = None,
    flags_search: str | None = None,
    settings_search: str | None = None,
    names_limit: int | None = None,
    descriptions_limit: int | None = None,
    flags_limit: int | None = None,
    settings_limit: int | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve a department artifact into fully hydrated resource pairs."""

    async def _fetch_artifact() -> list[Any]:
        if not department_id:
            return []
        async with pool.acquire() as conn:
            return await get_department_artifacts(
                conn,
                [department_id],
                active=None,
                names=True,
                descriptions=True,
                flags=True,
                settings=True,
            )

    async def _fetch_draft() -> list[Any]:
        if not draft_id:
            return []
        async with pool.acquire() as conn:
            return await get_department_drafts(conn, [draft_id])

    artifacts, drafts = await asyncio.gather(_fetch_artifact(), _fetch_draft())
    artifact = artifacts[0] if artifacts else None
    draft = drafts[0] if drafts else None

    merged = _merge_junction_ids(artifact, draft)

    async def _get_names_selected() -> list[Any]:
        return await get_names(pool, merged.name_ids, redis, bypass_cache)

    async def _search_names_suggestions() -> list[Any]:
        async with pool.acquire() as conn:
            return await search_names(
                conn,
                redis,
                search=names_search,
                limit_count=names_limit or 20,
                draft_id=group_id,
                exclude_ids=merged.name_ids,
                bypass_cache=bypass_cache,
                department=True,
            )

    async def _get_descriptions_selected() -> list[Any]:
        return await get_descriptions(pool,
            merged.description_ids,
            redis,
            bypass_cache,
        )

    async def _search_descriptions_suggestions() -> list[Any]:
        async with pool.acquire() as conn:
            return await search_descriptions(
                conn,
                redis,
                search=descriptions_search,
                limit_count=descriptions_limit or 20,
                draft_id=group_id,
                exclude_ids=merged.description_ids,
                bypass_cache=bypass_cache,
                department=True,
            )

    async def _get_flags_selected() -> list[Any]:
        return await get_flags(pool, merged.flag_ids, redis, bypass_cache)

    async def _search_flags_suggestions() -> list[Any]:
        async with pool.acquire() as conn:
            return await search_flags(
                conn,
                redis,
                search=flags_search,
                limit_count=flags_limit or 200,
                offset_count=0,
                exclude_ids=merged.flag_ids,
                flag_type="department_active",
                bypass_cache=bypass_cache,
            )

    async def _get_settings_selected() -> list[Any]:
        return await get_settings(pool, merged.setting_ids, redis, bypass_cache)

    async def _search_settings_suggestions() -> list[Any]:
        async with pool.acquire() as conn:
            return await search_settings(
                conn,
                redis,
                search=settings_search,
                limit_count=settings_limit or 20,
                offset_count=0,
                exclude_ids=merged.setting_ids,
                bypass_cache=bypass_cache,
                department=True,
            )

    (
        names_selected,
        names_suggestions,
        descriptions_selected,
        descriptions_suggestions,
        flags_selected,
        flags_suggestions,
        settings_selected,
        settings_suggestions,
    ) = await asyncio.gather(
        _get_names_selected(),
        _search_names_suggestions(),
        _get_descriptions_selected(),
        _search_descriptions_suggestions(),
        _get_flags_selected(),
        _search_flags_suggestions(),
        _get_settings_selected(),
        _search_settings_suggestions(),
    )

    filtered_flags_selected = [
        flag
        for flag in flags_selected
        if getattr(flag, "name", None) in DEPARTMENT_FLAG_NAMES
        or getattr(flag, "type", None) in DEPARTMENT_FLAG_NAMES
    ]
    filtered_flags_suggestions = [
        flag
        for flag in flags_suggestions
        if getattr(flag, "name", None) in DEPARTMENT_FLAG_NAMES
        or getattr(flag, "type", None) in DEPARTMENT_FLAG_NAMES
    ]

    pending_ids: set[UUID] = set()
    if draft:
        pending_ids.update(draft.pending_name_ids or [])
        pending_ids.update(draft.pending_description_ids or [])
        pending_ids.update(draft.pending_flag_ids or [])
        pending_ids.update(draft.pending_setting_ids or [])

    # Hydrate SVG icons onto each flag (icon_id → icon markup).
    async with pool.acquire() as conn:
        await hydrate_flag_icons(
            list(filtered_flags_selected) + list(filtered_flags_suggestions,), conn, redis, bypass_cache
        )

    return ArtifactContext(
        artifact_id=artifact.id if artifact else None,
        active=artifact.active if artifact else True,
        group_id=group_id,
        resources={
            "names": ResourcePair(
                selected=names_selected,
                suggestions=names_suggestions,
            ),
            "descriptions": ResourcePair(
                selected=descriptions_selected,
                suggestions=descriptions_suggestions,
            ),
            "flags": ResourcePair(
                selected=filtered_flags_selected,
                suggestions=filtered_flags_suggestions,
            ),
            "settings": ResourcePair(
                selected=settings_selected,
                suggestions=settings_suggestions,
            ),
        },
        entries={"draft_name": draft.name if draft else None, "pending_ids": pending_ids},
    )
