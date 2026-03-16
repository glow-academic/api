"""Tool permissions context + shared save helpers.

Permissions context:
  1. resolve_tool_permissions_context — lightweight access + edit check

Shared save helpers (used by both create and update):
  2. resolve_tool_values — raw string → resource ID resolution
  3. create_denormalized_snapshot — hydrate IDs → tools_resource snapshot

Composes existing black-box fetchers — no raw SQL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.agent.search import search_agents
from app.tools.artifacts.tool.get import (
    get_tools as get_tool_artifacts,
)
from app.tools.resources.artifacts.get import get_artifacts
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.tools.resources.operations.get import get_operations
from app.tools.resources.tools.create import (
    create_tool as create_tool_resource,
)

if TYPE_CHECKING:
    from app.infra.tool.create import CreateToolItem, ToolFieldError
    from app.infra.tool.types import (
        UpdateToolItem,
    )


@dataclass(frozen=True)
class ToolPermissionsContext:
    """Lightweight context for tool permission checks."""

    exists: bool
    active_agent_count: int


async def resolve_tool_permissions_context(
    conn: asyncpg.Connection,
    tool_id: UUID,
) -> ToolPermissionsContext:
    """Fetch just what's needed for tool permission checks.

    Two black-box tool calls:
      1. get_tool_artifacts → exists check
      2. search_agents(tool_ids=...) → any active agents using this tool?
    """
    artifacts = await get_tool_artifacts(conn, [tool_id])

    if not artifacts:
        return ToolPermissionsContext(
            exists=False,
            active_agent_count=0,
        )

    _, total = await search_agents(
        conn,
        tool_ids=[tool_id],
        active_only=True,
        limit_count=1,
    )

    return ToolPermissionsContext(
        exists=True,
        active_agent_count=total,
    )


# ---------------------------------------------------------------------------
# Shared save helpers — used by both tool_create and tool_update
# ---------------------------------------------------------------------------


async def resolve_tool_values(
    conn: asyncpg.Connection,
    redis: Redis,
    item: CreateToolItem | UpdateToolItem,
    is_create: bool,
) -> list[ToolFieldError]:
    """Resolve raw value fields to resource IDs (mutates item in place).

    For 'create' resources (name, description):
      Creates a new resource via the create tool.

    Returns a list of errors (empty if all resolved).
    """
    from app.infra.tool.create import ToolFieldError

    errors: list[ToolFieldError] = []

    # --- Create resources ---

    if item.name is not None and item.name_id is None:
        result = await create_name(conn, item.name, redis)
        item.name_id = result.id

    if item.description is not None and item.description_id is None:
        result = await create_description(conn, item.description, redis)
        item.description_id = result.id

    # --- Validate required fields (create only) ---

    if is_create:
        if item.name_id is None and item.name is None:
            errors.append(ToolFieldError(field="name", message="Name is required"))

    return errors


async def create_denormalized_snapshot(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    id: UUID | None = None,
    name_id: UUID | None,
    description_id: UUID | None,
    department_ids: list[UUID] | None = None,
    args_ids: list[UUID] | None = None,
    args_output_ids: list[UUID] | None = None,
    operation_ids: list[UUID] | None = None,
    artifact_ids: list[UUID] | None = None,
) -> UUID:
    """Create a tools_resource snapshot by hydrating IDs to values.

    Each parallel branch acquires its own connection from the pool.
    """

    async def _get_names() -> list:
        if not name_id:
            return []
        async with pool.acquire() as conn:
            return await get_names(conn, [name_id], redis, bypass_cache=True)

    async def _get_descriptions() -> list:
        if not description_id:
            return []
        async with pool.acquire() as conn:
            return await get_descriptions(
                conn, [description_id], redis, bypass_cache=True
            )

    async def _get_operations() -> list:
        if not operation_ids:
            return []
        async with pool.acquire() as conn:
            return await get_operations(conn, operation_ids, redis, bypass_cache=True)

    async def _get_artifacts() -> list:
        if not artifact_ids:
            return []
        async with pool.acquire() as conn:
            return await get_artifacts(conn, artifact_ids, redis, bypass_cache=True)

    names, descriptions, operations, artifacts = await asyncio.gather(
        _get_names(),
        _get_descriptions(),
        _get_operations(),
        _get_artifacts(),
    )

    async with pool.acquire() as conn:
        result = await create_tool_resource(
            conn,
            id=id,
            name=names[0].name if names else "",
            description=descriptions[0].description if descriptions else "",
            department_ids=department_ids,
            args_ids=args_ids,
            args_output_ids=args_output_ids,
            operation=operations[0].operation if operations else None,
            artifacts=[item.artifact for item in artifacts],
            redis=redis,
        )
    return result.id
