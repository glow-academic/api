"""Resolve auth artifact context — merged junctions + hydrated resources."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.flag_icons import hydrate_flag_icons
from app.infra.types import ArtifactContext, ResourcePair
from app.tools.artifacts.auth.get import get_auths as get_auth_artifacts
from app.tools.entries.auth_drafts.get import get_auth_drafts
from app.tools.resources.departments.get import get_departments
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.search import search_flags
from app.tools.resources.items.get import get_items
from app.tools.resources.items.search import search_items
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names
from app.tools.resources.protocols.get import get_protocols
from app.tools.resources.protocols.search import search_protocols
from app.tools.resources.slugs.get import get_slugs
from app.tools.resources.slugs.search import search_slugs

AUTH_FLAG_NAMES = {"auth_active"}


@dataclass
class _MergedIds:
    name_ids: list[UUID]
    description_ids: list[UUID]
    flag_ids: list[UUID]
    department_ids: list[UUID]
    item_ids: list[UUID]
    protocol_ids: list[UUID]
    slug_ids: list[UUID]


async def resolve_auth_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    auth_id: UUID | None,
    group_id: UUID,
    draft_id: UUID | None = None,
    names_search: str | None = None,
    descriptions_search: str | None = None,
    departments_search: str | None = None,
    protocols_search: str | None = None,
    slugs_search: str | None = None,
    items_search: str | None = None,
    names_limit: int | None = None,
    descriptions_limit: int | None = None,
    departments_limit: int | None = None,
    protocols_limit: int | None = None,
    slugs_limit: int | None = None,
    items_limit: int | None = None,
    names_selected_only: bool | None = None,
    descriptions_selected_only: bool | None = None,
    departments_selected_only: bool | None = None,
    protocols_selected_only: bool | None = None,
    slugs_selected_only: bool | None = None,
    items_selected_only: bool | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve an auth artifact into fully hydrated resources for the GET endpoint."""

    async def _fetch_artifact() -> list:
        if not auth_id:
            return []
        async with pool.acquire() as conn:
            return await get_auth_artifacts(
                conn,
                [auth_id],
                active=None,
                names=True,
                descriptions=True,
                departments=True,
                flags=True,
                items=True,
                protocols=True,
                slugs=True,
            )

    async def _fetch_draft() -> list:
        if not draft_id:
            return []
        async with pool.acquire() as conn:
            return await get_auth_drafts(conn, [draft_id])

    artifacts, drafts = await asyncio.gather(_fetch_artifact(), _fetch_draft())
    artifact = artifacts[0] if artifacts else None
    draft = drafts[0] if drafts else None

    merged = _merge_junction_ids(artifact, draft)
    active = artifact.active if artifact else True

    async def _get_names() -> list:
        return await get_names(pool, merged.name_ids, redis, bypass_cache)

    async def _search_names() -> list:
        async with pool.acquire() as conn:
            return await search_names(
                conn,
                redis,
                search=names_search,
                limit_count=names_limit or 20,
                draft_id=group_id,
                suggest_source="selected" if names_selected_only else "all",
                exclude_ids=merged.name_ids,
                bypass_cache=bypass_cache,
                auth=True,
            )

    async def _get_descriptions() -> list:
        return await get_descriptions(pool, merged.description_ids, redis, bypass_cache)

    async def _search_descriptions() -> list:
        async with pool.acquire() as conn:
            return await search_descriptions(
                conn,
                redis,
                search=descriptions_search,
                limit_count=descriptions_limit or 20,
                draft_id=group_id,
                suggest_source="selected" if descriptions_selected_only else "all",
                exclude_ids=merged.description_ids,
                bypass_cache=bypass_cache,
                auth=True,
            )

    async def _get_flags() -> list:
        return await get_flags(pool, merged.flag_ids, redis, bypass_cache)

    async def _search_flags() -> list:
        async with pool.acquire() as conn:
            # Don't intersect on auth_flags_junction — for a fresh auth draft
            # no junction rows exist yet. AUTH_FLAG_NAMES below is the real
            # filter for the catalog.
            flags = await search_flags(
                conn,
                redis,
                search=None,
                limit_count=50,
                offset_count=0,
                exclude_ids=merged.flag_ids,
                bypass_cache=bypass_cache,
            )
        return [flag for flag in flags if getattr(flag, "name", None) in AUTH_FLAG_NAMES]

    async def _get_departments() -> list:
        return await get_departments(pool, merged.department_ids, redis, bypass_cache)

    async def _search_departments() -> list:
        async with pool.acquire() as conn:
            # Departments are a universal catalog — don't intersect on
            # auth_departments_junction or fresh drafts see nothing.
            return await search_departments(
                conn,
                redis,
                search=departments_search,
                limit_count=departments_limit or 20,
                draft_id=group_id,
                suggest_source="selected" if departments_selected_only else "all",
                exclude_ids=merged.department_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_protocols() -> list:
        return await get_protocols(pool, merged.protocol_ids, redis, bypass_cache)

    async def _search_protocols() -> list:
        async with pool.acquire() as conn:
            return await search_protocols(
                conn,
                redis,
                search=protocols_search,
                limit_count=protocols_limit or 20,
                draft_id=group_id,
                suggest_source="selected" if protocols_selected_only else "all",
                exclude_ids=merged.protocol_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_slugs() -> list:
        return await get_slugs(pool, merged.slug_ids, redis, bypass_cache)

    async def _search_slugs() -> list:
        async with pool.acquire() as conn:
            return await search_slugs(
                conn,
                redis,
                search=slugs_search,
                limit_count=slugs_limit or 20,
                draft_id=group_id,
                suggest_source="selected" if slugs_selected_only else "all",
                exclude_ids=merged.slug_ids,
                bypass_cache=bypass_cache,
            )

    async def _get_items() -> list:
        return await get_items(pool, merged.item_ids, redis, bypass_cache)

    async def _search_items() -> list:
        async with pool.acquire() as conn:
            return await search_items(
                conn,
                redis,
                search=items_search,
                limit_count=items_limit or 20,
                exclude_ids=merged.item_ids,
                bypass_cache=bypass_cache,
                auth=True,
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
        protocols_selected,
        protocols_suggestions,
        slugs_selected,
        slugs_suggestions,
        items_selected,
        items_suggestions,
    ) = await asyncio.gather(
        _get_names(),
        _search_names(),
        _get_descriptions(),
        _search_descriptions(),
        _get_flags(),
        _search_flags(),
        _get_departments(),
        _search_departments(),
        _get_protocols(),
        _search_protocols(),
        _get_slugs(),
        _search_slugs(),
        _get_items(),
        _search_items(),
    )

    pending_ids: set[UUID] = set()
    if draft is not None:
        pending_ids.update(draft.pending_name_ids or [])
        pending_ids.update(draft.pending_description_ids or [])
        pending_ids.update(draft.pending_flag_ids or [])
        pending_ids.update(draft.pending_department_ids or [])
        pending_ids.update(draft.pending_protocol_ids or [])
        pending_ids.update(draft.pending_slug_ids or [])
        pending_ids.update(draft.pending_item_ids or [])

    # Hydrate SVG icons onto each flag (icon_id → icon markup).
    async with pool.acquire() as conn:
        await hydrate_flag_icons(
            list(flags_selected) + list(flags_suggestions), conn, redis, bypass_cache
        )

    return ArtifactContext(
        artifact_id=artifact.id if artifact else None,
        active=active,
        group_id=group_id,
        resources={
            "names": ResourcePair(selected=names_selected, suggestions=names_suggestions),
            "descriptions": ResourcePair(selected=descriptions_selected, suggestions=descriptions_suggestions),
            "flags": ResourcePair(selected=flags_selected, suggestions=flags_suggestions),
            "departments": ResourcePair(selected=departments_selected, suggestions=departments_suggestions),
            "protocols": ResourcePair(selected=protocols_selected, suggestions=protocols_suggestions),
            "slugs": ResourcePair(selected=slugs_selected, suggestions=slugs_suggestions),
            "items": ResourcePair(selected=items_selected, suggestions=items_suggestions),
        },
        entries={"draft_name": draft.name if draft else None, "pending_ids": pending_ids},
    )


def _merge_junction_ids(artifact, draft) -> _MergedIds:
    """Merge artifact junction IDs with draft overrides."""
    name_ids = list(artifact.name_ids or []) if artifact else []
    description_ids = list(artifact.description_ids or []) if artifact else []
    flag_ids = list(artifact.flag_ids or []) if artifact else []
    department_ids = list(artifact.department_ids or []) if artifact else []
    item_ids = list(artifact.item_ids or []) if artifact else []
    protocol_ids = list(artifact.protocol_ids or []) if artifact else []
    slug_ids = list(artifact.slug_ids or []) if artifact else []

    if draft is not None:
        name_ids = list(draft.name_ids or [])
        description_ids = list(draft.description_ids or [])
        flag_ids = list(draft.flag_ids or [])
        department_ids = list(draft.department_ids or [])
        item_ids = list(draft.item_ids or [])
        protocol_ids = list(draft.protocol_ids or [])
        slug_ids = list(draft.slug_ids or [])

    return _MergedIds(
        name_ids=name_ids,
        description_ids=description_ids,
        flag_ids=flag_ids,
        department_ids=department_ids,
        item_ids=item_ids,
        protocol_ids=protocol_ids,
        slug_ids=slug_ids,
    )
