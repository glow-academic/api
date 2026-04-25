"""Resolve tool artifact context — merged junctions + hydrated resources."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.helpers import dedupe_by_id
from app.infra.flag_icons import hydrate_flag_icons
from app.infra.types import ArtifactContext, ResourcePair
from app.tools.artifacts.tool.get import get_tools as get_tool_artifacts
from app.tools.entries.tool_drafts.get import get_tool_drafts
from app.tools.resources.arg_positions.get import get_arg_positions
from app.tools.resources.arg_positions.search import search_arg_positions
from app.tools.resources.args.get import get_args
from app.tools.resources.args.search import search_args
from app.tools.resources.args_outputs.get import get_args_outputs
from app.tools.resources.args_outputs.search import search_args_outputs
from app.tools.resources.departments.get import get_departments
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.search import search_flags
from app.tools.resources.instructions.get import get_instructions
from app.tools.resources.instructions.search import search_instructions
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names
from app.tools.resources.permissions.get import get_permissions
from app.tools.resources.permissions.search import search_permissions

TOOL_FLAG_TYPES = {"tool_active"}


@dataclass
class _MergedIds:
    name_ids: list[UUID]
    description_ids: list[UUID]
    flag_ids: list[UUID]
    department_ids: list[UUID]
    args_ids: list[UUID]
    arg_position_ids: list[UUID]
    args_output_ids: list[UUID]
    permission_ids: list[UUID]
    instruction_ids: list[UUID]


def _merge_junction_ids(artifact, draft) -> _MergedIds:
    name_ids = list(artifact.name_ids or []) if artifact else []
    description_ids = list(artifact.description_ids or []) if artifact else []
    flag_ids = list(artifact.flag_ids or []) if artifact else []
    department_ids = list(artifact.department_ids or []) if artifact else []
    args_ids = list(artifact.args_ids or []) if artifact else []
    arg_position_ids = list(artifact.arg_positions_ids or []) if artifact else []
    args_output_ids = list(artifact.args_outputs_ids or []) if artifact else []
    permission_ids = list(artifact.permission_ids or []) if artifact else []
    instruction_ids = list(artifact.instruction_ids or []) if artifact else []

    if draft:
        if draft.name_ids:
            name_ids = list(draft.name_ids)
        if draft.description_ids:
            description_ids = list(draft.description_ids)
        if draft.flag_ids:
            flag_ids = list(draft.flag_ids)
        if getattr(draft, "department_ids", None):
            department_ids = list(draft.department_ids)
        if draft.arg_ids:
            args_ids = list(draft.arg_ids)
        if draft.arg_position_ids:
            arg_position_ids = list(draft.arg_position_ids)
        if draft.args_output_ids:
            args_output_ids = list(draft.args_output_ids)
        if draft.permission_ids:
            permission_ids = list(draft.permission_ids)
        if getattr(draft, "instruction_ids", None):
            instruction_ids = list(draft.instruction_ids)

    return _MergedIds(
        name_ids=name_ids,
        description_ids=description_ids,
        flag_ids=flag_ids,
        department_ids=department_ids,
        args_ids=args_ids,
        arg_position_ids=arg_position_ids,
        args_output_ids=args_output_ids,
        permission_ids=permission_ids,
        instruction_ids=instruction_ids,
    )


async def resolve_tool_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    tool_id: UUID | None,
    group_id: UUID,
    draft_id: UUID | None = None,
    names_search: str | None = None,
    descriptions_search: str | None = None,
    flags_search: str | None = None,
    departments_search: str | None = None,
    args_search: str | None = None,
    arg_positions_search: str | None = None,
    args_outputs_search: str | None = None,
    permissions_search: str | None = None,
    instructions_search: str | None = None,
    names_limit: int | None = None,
    descriptions_limit: int | None = None,
    flags_limit: int | None = None,
    departments_limit: int | None = None,
    args_limit: int | None = None,
    arg_positions_limit: int | None = None,
    args_outputs_limit: int | None = None,
    permissions_limit: int | None = None,
    instructions_limit: int | None = None,
    names_selected_only: bool | None = None,
    descriptions_selected_only: bool | None = None,
    flags_selected_only: bool | None = None,
    departments_selected_only: bool | None = None,
    args_selected_only: bool | None = None,
    arg_positions_selected_only: bool | None = None,
    args_outputs_selected_only: bool | None = None,
    permissions_selected_only: bool | None = None,
    instructions_selected_only: bool | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve a tool artifact into fully hydrated resources."""

    async def _fetch_artifact() -> list:
        if not tool_id:
            return []
        async with pool.acquire() as conn:
            return await get_tool_artifacts(
                conn,
                [tool_id],
                active=None,
                names=True,
                descriptions=True,
                flags=True,
                departments=True,
                args=True,
                arg_positions=True,
                args_outputs=True,
                permissions=True,
                instructions=True,
            )

    async def _fetch_draft() -> list:
        if not draft_id:
            return []
        async with pool.acquire() as conn:
            return await get_tool_drafts(conn, [draft_id])

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
                tool=True,
            )

    async def _get_descriptions() -> list:
        async with pool.acquire() as conn:
            return await get_descriptions(conn, merged.description_ids, redis, bypass_cache)

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
                tool=True,
            )

    async def _get_flags() -> list:
        async with pool.acquire() as conn:
            return await get_flags(conn, merged.flag_ids, redis, bypass_cache)

    async def _search_flags() -> list:
        async with pool.acquire() as conn:
            # Don't filter on tool_flags_junction — new tools have no
            # junction rows. TOOL_FLAG_TYPES post-filter narrows below.
            results = await search_flags(
                conn,
                redis,
                search=flags_search,
                limit_count=flags_limit or 200,
                exclude_ids=merged.flag_ids,
                bypass_cache=bypass_cache,
            )
        return [flag for flag in results if getattr(flag, "type", None) in TOOL_FLAG_TYPES]

    async def _get_departments() -> list:
        async with pool.acquire() as conn:
            return await get_departments(
                conn, merged.department_ids, redis, bypass_cache
            )

    async def _search_departments_facet() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn,
                redis,
                search=departments_search,
                limit_count=departments_limit or 20,
                offset_count=0,
                suggest_source="selected" if departments_selected_only else "all",
                exclude_ids=merged.department_ids,
                bypass_cache=bypass_cache,
                tool=True,
            )

    async def _get_args() -> list:
        async with pool.acquire() as conn:
            return await get_args(conn, merged.args_ids, redis, bypass_cache=bypass_cache)

    async def _search_args() -> list:
        async with pool.acquire() as conn:
            return await search_args(
                conn,
                redis,
                search=args_search,
                limit_count=args_limit or 20,
                draft_id=group_id,
                suggest_source="selected" if args_selected_only else "all",
                exclude_ids=merged.args_ids,
                bypass_cache=bypass_cache,
                tool=True,
            )

    async def _get_arg_positions() -> list:
        async with pool.acquire() as conn:
            return await get_arg_positions(
                conn,
                merged.arg_position_ids,
                redis,
                bypass_cache=bypass_cache,
            )

    async def _search_arg_positions() -> list:
        if arg_positions_search:
            return []
        async with pool.acquire() as conn:
            return await search_arg_positions(
                conn,
                redis,
                limit_count=arg_positions_limit or 100,
                exclude_ids=merged.arg_position_ids,
                args_ids=merged.args_ids if arg_positions_selected_only else None,
                bypass_cache=bypass_cache,
                tool=True,
            )

    async def _get_args_outputs() -> list:
        async with pool.acquire() as conn:
            return await get_args_outputs(
                conn,
                merged.args_output_ids,
                redis,
                bypass_cache=bypass_cache,
            )

    async def _search_args_outputs() -> list:
        async with pool.acquire() as conn:
            return await search_args_outputs(
                conn,
                redis,
                search=args_outputs_search,
                limit_count=args_outputs_limit or 20,
                draft_id=group_id,
                suggest_source="selected" if args_outputs_selected_only else "all",
                exclude_ids=merged.args_output_ids,
                args_ids=merged.args_ids if merged.args_ids else None,
                bypass_cache=bypass_cache,
                tool=True,
            )

    async def _get_permissions() -> list:
        async with pool.acquire() as conn:
            return await get_permissions(conn, merged.permission_ids, redis, bypass_cache)

    async def _search_permissions() -> list:
        async with pool.acquire() as conn:
            results = await search_permissions(
                conn,
                redis,
                search=permissions_search,
                limit_count=permissions_limit or 100,
                bypass_cache=bypass_cache,
            )
        selected_ids = set(merged.permission_ids)
        return [item for item in results if item.id not in selected_ids]

    async def _get_instructions() -> list:
        async with pool.acquire() as conn:
            return await get_instructions(
                conn, merged.instruction_ids, redis, bypass_cache=bypass_cache,
            )

    async def _search_instructions() -> list:
        async with pool.acquire() as conn:
            # Don't intersect on tool_instructions_junction — a fresh tool
            # draft has no junction rows yet, which would zero out the
            # catalog. Pattern matches auth/cohort/etc. catalog searches.
            return await search_instructions(
                conn,
                redis,
                search=instructions_search,
                limit_count=instructions_limit or 20,
                draft_id=group_id,
                suggest_source="selected" if instructions_selected_only else "all",
                exclude_ids=merged.instruction_ids,
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
        args_selected,
        args_suggestions,
        arg_positions_selected,
        arg_positions_suggestions,
        args_outputs_selected,
        args_outputs_suggestions,
        permissions_selected,
        permissions_suggestions,
        instructions_selected,
        instructions_suggestions,
    ) = await asyncio.gather(
        _get_names(),
        _search_names(),
        _get_descriptions(),
        _search_descriptions(),
        _get_flags(),
        _search_flags(),
        _get_departments(),
        _search_departments_facet(),
        _get_args(),
        _search_args(),
        _get_arg_positions(),
        _search_arg_positions(),
        _get_args_outputs(),
        _search_args_outputs(),
        _get_permissions(),
        _search_permissions(),
        _get_instructions(),
        _search_instructions(),
    )

    pending_ids: set[UUID] = set()
    if draft:
        pending_ids.update(draft.pending_name_ids or [])
        pending_ids.update(draft.pending_description_ids or [])
        pending_ids.update(draft.pending_flag_ids or [])
        pending_ids.update(draft.pending_department_ids or [])
        pending_ids.update(draft.pending_arg_ids or [])
        pending_ids.update(draft.pending_arg_position_ids or [])
        pending_ids.update(draft.pending_args_output_ids or [])
        pending_ids.update(draft.pending_permission_ids or [])
        pending_ids.update(getattr(draft, "pending_instruction_ids", None) or [])

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
            "names": ResourcePair(
                selected=dedupe_by_id(names_selected),
                suggestions=dedupe_by_id(names_suggestions),
            ),
            "descriptions": ResourcePair(
                selected=dedupe_by_id(descriptions_selected),
                suggestions=dedupe_by_id(descriptions_suggestions),
            ),
            "flags": ResourcePair(
                selected=dedupe_by_id(flags_selected),
                suggestions=dedupe_by_id(flags_suggestions),
            ),
            "departments": ResourcePair(
                selected=dedupe_by_id(departments_selected),
                suggestions=dedupe_by_id(departments_suggestions),
            ),
            "args": ResourcePair(
                selected=dedupe_by_id(args_selected),
                suggestions=dedupe_by_id(args_suggestions),
            ),
            "arg_positions": ResourcePair(
                selected=dedupe_by_id(arg_positions_selected),
                suggestions=dedupe_by_id(arg_positions_suggestions),
            ),
            "args_outputs": ResourcePair(
                selected=dedupe_by_id(args_outputs_selected),
                suggestions=dedupe_by_id(args_outputs_suggestions),
            ),
            "permissions": ResourcePair(
                selected=dedupe_by_id(permissions_selected),
                suggestions=dedupe_by_id(permissions_suggestions),
            ),
            "instructions": ResourcePair(
                selected=dedupe_by_id(instructions_selected),
                suggestions=dedupe_by_id(instructions_suggestions),
            ),
        },
        entries={"pending_ids": pending_ids},
    )


resolve_tool_artifact_context = resolve_tool_context
