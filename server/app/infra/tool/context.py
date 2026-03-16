"""Resolve tool artifact context — merged junctions + hydrated resources.

Given a tool_id (and optional draft_id), fetches the published artifact
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
from app.tools.artifacts.tool.get import (
    get_tools as get_tool_artifacts,
)
from app.tools.entries.tool_drafts.get import get_tool_drafts

# Resource get fetchers (by known IDs)
from app.tools.resources.arg_positions.get import get_arg_positions

# Resource search fetchers (bounded, paginated)
from app.tools.resources.arg_positions.search import search_arg_positions
from app.tools.resources.args.get import get_args
from app.tools.resources.args.search import search_args
from app.tools.resources.args_outputs.get import get_args_outputs
from app.tools.resources.args_outputs.search import search_args_outputs
from app.tools.resources.artifacts.get import get_artifacts
from app.tools.resources.artifacts.search import search_artifacts
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names
from app.tools.resources.operations.get import get_operations
from app.tools.resources.operations.search import search_operations

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOOL_FLAG_NAMES = {
    "tool_active",
}


# ---------------------------------------------------------------------------
# resolve_tool_artifact_context
# ---------------------------------------------------------------------------


async def resolve_tool_artifact_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    tool_id: UUID | None,
    group_id: UUID,
    draft_id: UUID | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve a tool artifact into fully hydrated resources for the GET endpoint.

    Steps:
      1. Fetch artifact + draft in parallel -> merge IDs
      2. Parallel hydrate: get (selected) + search (suggestions) per resource
      3. Assemble ArtifactContext with ResourcePairs
    """

    # Step 1: fetch artifact + draft in parallel

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
                args=True,
                arg_positions=True,
                args_outputs=True,
                artifacts=True,
                operations=True,
            )

    async def _fetch_draft() -> list:
        if not draft_id:
            return []
        async with pool.acquire() as conn:
            return await get_tool_drafts(conn, [draft_id])

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
                tool=True,
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
                tool=True,
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
                tool=True,
            )

    async def _get_args() -> list:
        async with pool.acquire() as conn:
            return await get_args(
                conn, merged.args_ids, redis, bypass_cache=bypass_cache
            )

    async def _search_args() -> list:
        async with pool.acquire() as conn:
            return await search_args(
                conn,
                redis,
                suggest_source="linked",
                exclude_ids=merged.args_ids,
                bypass_cache=bypass_cache,
                tool=True,
            )

    async def _get_arg_positions() -> list:
        async with pool.acquire() as conn:
            return await get_arg_positions(
                conn, merged.arg_position_ids, redis, bypass_cache=bypass_cache
            )

    async def _search_arg_positions() -> list:
        async with pool.acquire() as conn:
            return await search_arg_positions(
                conn,
                redis,
                limit_count=100,
                offset_count=0,
                exclude_ids=merged.arg_position_ids,
                args_ids=merged.args_ids,
                bypass_cache=bypass_cache,
                tool=True,
            )

    async def _get_args_outputs() -> list:
        async with pool.acquire() as conn:
            return await get_args_outputs(
                conn, merged.args_outputs_ids, redis, bypass_cache=bypass_cache
            )

    async def _search_args_outputs() -> list:
        async with pool.acquire() as conn:
            return await search_args_outputs(
                conn,
                redis,
                suggest_source="linked",
                exclude_ids=merged.args_outputs_ids,
                bypass_cache=bypass_cache,
                tool=True,
            )

    async def _get_artifacts() -> list:
        async with pool.acquire() as conn:
            return await get_artifacts(conn, merged.artifact_ids, redis, bypass_cache)

    async def _search_artifacts() -> list:
        async with pool.acquire() as conn:
            return await search_artifacts(
                conn,
                redis,
                exclude_ids=merged.artifact_ids,
                bypass_cache=bypass_cache,
                tool=True,
            )

    async def _get_operations() -> list:
        async with pool.acquire() as conn:
            return await get_operations(conn, merged.operation_ids, redis, bypass_cache)

    async def _search_operations() -> list:
        async with pool.acquire() as conn:
            return await search_operations(
                conn,
                redis,
                exclude_ids=merged.operation_ids,
                bypass_cache=bypass_cache,
                tool=True,
            )

    (
        names_selected,
        names_suggestions,
        descriptions_selected,
        descriptions_suggestions,
        flags_selected,
        flags_suggestions,
        args_selected,
        args_suggestions,
        arg_positions_selected,
        arg_positions_suggestions,
        args_outputs_selected,
        args_outputs_suggestions,
        artifacts_selected,
        artifacts_suggestions,
        operations_selected,
        operations_suggestions,
    ) = await asyncio.gather(
        _get_names(),
        _search_names(),
        _get_descriptions(),
        _search_descriptions(),
        _get_flags(),
        _search_flags(),
        _get_args(),
        _search_args(),
        _get_arg_positions(),
        _search_arg_positions(),
        _get_args_outputs(),
        _search_args_outputs(),
        _get_artifacts(),
        _search_artifacts(),
        _get_operations(),
        _search_operations(),
    )

    # Filter flags to tool-specific types
    flags_suggestions_filtered = [
        f for f in flags_suggestions if getattr(f, "name", None) in TOOL_FLAG_NAMES
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
            "args": ResourcePair(selected=args_selected, suggestions=args_suggestions),
            "arg_positions": ResourcePair(
                selected=arg_positions_selected, suggestions=arg_positions_suggestions
            ),
            "args_outputs": ResourcePair(
                selected=args_outputs_selected, suggestions=args_outputs_suggestions
            ),
            "artifacts": ResourcePair(
                selected=artifacts_selected, suggestions=artifacts_suggestions
            ),
            "operations": ResourcePair(
                selected=operations_selected, suggestions=operations_suggestions
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
    args_ids: list[UUID]
    arg_position_ids: list[UUID]
    args_outputs_ids: list[UUID]
    artifact_ids: list[UUID]
    operation_ids: list[UUID]


def _merge_junction_ids(artifact, draft) -> _MergedIds:
    """Merge artifact junction IDs with draft overrides."""
    name_ids = list(artifact.name_ids or []) if artifact else []
    description_ids = list(artifact.description_ids or []) if artifact else []
    flag_ids = list(artifact.flag_ids or []) if artifact else []
    args_ids = list(artifact.args_ids or []) if artifact else []
    arg_position_ids = list(artifact.arg_positions_ids or []) if artifact else []
    args_outputs_ids = list(artifact.args_outputs_ids or []) if artifact else []
    artifact_ids = list(artifact.artifact_ids or []) if artifact else []
    operation_ids = list(artifact.operation_ids or []) if artifact else []

    # Draft overrides (if present) — ignore profile_ids from draft
    if draft:
        if draft.name_ids:
            name_ids = list(draft.name_ids)
        if draft.description_ids:
            description_ids = list(draft.description_ids)
        if draft.flag_ids:
            flag_ids = list(draft.flag_ids)
        if draft.arg_ids:
            args_ids = list(draft.arg_ids)
        if draft.arg_position_ids:
            arg_position_ids = list(draft.arg_position_ids)
        if draft.args_output_ids:
            args_outputs_ids = list(draft.args_output_ids)
        if draft.artifact_ids:
            artifact_ids = list(draft.artifact_ids)
        if draft.operation_ids:
            operation_ids = list(draft.operation_ids)

    return _MergedIds(
        name_ids=name_ids,
        description_ids=description_ids,
        flag_ids=flag_ids,
        args_ids=args_ids,
        arg_position_ids=arg_position_ids,
        args_outputs_ids=args_outputs_ids,
        artifact_ids=artifact_ids,
        operation_ids=operation_ids,
    )


async def _empty() -> list:
    return []
