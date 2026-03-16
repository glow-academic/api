"""Agent permissions context + shared save helpers.

Permissions context:
  1. resolve_agent_permissions_context — lightweight access + edit check

Shared save helpers (used by both create and update):
  2. resolve_agent_values — raw string → resource ID resolution
  3. create_denormalized_snapshot — hydrate IDs → agents_resource snapshot

Composes existing black-box fetchers — no raw SQL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.agent.get import (
    get_agents as get_agent_artifacts,
)
from app.tools.resources.agents.create import (
    create_agent as create_agent_resource,
)
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.tools.resources.voices.get import get_voices

if TYPE_CHECKING:
    from app.infra.agent.create import AgentFieldError, CreateAgentItem
    from app.infra.agent.types import (
        UpdateAgentItem,
    )


@dataclass(frozen=True)
class AgentPermissionsContext:
    """Lightweight context for agent permission checks."""

    exists: bool
    department_ids: list[UUID]


async def resolve_agent_permissions_context(
    conn: asyncpg.Connection,
    agent_id: UUID,
) -> AgentPermissionsContext:
    """Fetch just what's needed for agent permission checks.

    Single black-box tool call:
      1. get_agent_artifacts → department_ids
    """
    artifacts = await get_agent_artifacts(
        conn,
        [agent_id],
        departments=True,
    )

    if not artifacts:
        return AgentPermissionsContext(
            exists=False,
            department_ids=[],
        )

    artifact = artifacts[0]
    department_ids = list(artifact.department_ids or [])

    return AgentPermissionsContext(
        exists=True,
        department_ids=department_ids,
    )


# ---------------------------------------------------------------------------
# Shared save helpers — used by both agent_create and agent_update
# ---------------------------------------------------------------------------


async def resolve_agent_values(
    conn: asyncpg.Connection,
    redis: Redis,
    item: CreateAgentItem | UpdateAgentItem,
    is_create: bool,
) -> list[AgentFieldError]:
    """Resolve raw value fields to resource IDs (mutates item in place).

    For 'create' resources (name, description):
      Creates a new resource via the create tool.
    For 'match' resources (departments):
      Searches by name via the search tool, matches exact (case-insensitive).

    Returns a list of errors (empty if all resolved).
    """
    from app.infra.agent.create import AgentFieldError

    errors: list[AgentFieldError] = []

    # --- Create resources ---

    if item.name is not None and item.name_id is None:
        result = await create_name(conn, item.name, redis)
        item.name_id = result.id

    if item.description is not None and item.description_id is None:
        result = await create_description(conn, item.description, redis)
        item.description_id = result.id

    # --- Match resources ---

    if item.departments is not None and item.department_ids is None:
        all_depts = await search_departments(
            conn,
            redis,
            search=None,
            limit_count=1000,
        )
        dept_name_map = {d.name.lower(): d.id for d in all_depts if d.name and d.id}
        resolved_ids = []
        for dept_name in item.departments:
            dept_id = dept_name_map.get(dept_name.lower())
            if dept_id:
                resolved_ids.append(dept_id)
            else:
                errors.append(
                    AgentFieldError(
                        field="departments",
                        message=f'Department "{dept_name}" not found',
                    )
                )
        if not any(e.field == "departments" for e in errors):
            item.department_ids = resolved_ids

    # --- Validate required fields (create only) ---

    if is_create:
        if item.name_id is None and item.name is None:
            errors.append(AgentFieldError(field="name", message="Name is required"))

    return errors


async def create_denormalized_snapshot(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    id: UUID | None = None,
    name_id: UUID | None,
    description_id: UUID | None,
    department_ids: list[UUID] | None = None,
    model_id: UUID | None = None,
    prompt_id: UUID | None = None,
    rubric_id: UUID | None = None,
    tool_ids: list[UUID] | None = None,
    instruction_ids: list[UUID] | None = None,
    voice_ids: list[UUID] | None = None,
) -> UUID:
    """Create an agents_resource snapshot by hydrating IDs to values.

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

    async def _get_voices() -> list:
        if not voice_ids:
            return []
        async with pool.acquire() as conn:
            return await get_voices(conn, voice_ids, redis, bypass_cache=True)

    names, descriptions, voices = await asyncio.gather(
        _get_names(),
        _get_descriptions(),
        _get_voices(),
    )

    voice_strings = [v.voice for v in voices] if voices else None

    async with pool.acquire() as conn:
        result = await create_agent_resource(
            conn,
            id=id,
            name=names[0].name if names else "",
            description=descriptions[0].description if descriptions else "",
            department_ids=department_ids,
            model_id=model_id,
            prompt_id=prompt_id,
            rubric_id=rubric_id,
            tool_ids=tool_ids,
            instruction_ids=instruction_ids,
            voices=voice_strings,
            redis=redis,
        )
    return result.id
