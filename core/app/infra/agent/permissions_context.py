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

from app.infra.department_id_resolution import (
    resolve_department_ids_to_resource_ids,
)
from app.tools.artifacts.agent.get import (
    get_agents as get_agent_artifacts,
)
from app.tools.artifacts.model.get import (
    get_models as get_model_artifacts,
)
from app.tools.artifacts.rubric.get import (
    get_rubrics as get_rubric_artifacts,
)
from app.tools.artifacts.tool.get import (
    get_tools as get_tool_artifacts,
)
from app.tools.resources.agents.create import (
    create_agent as create_agent_resource,
)
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.tools.resources.voices.get import get_voices

if TYPE_CHECKING:
    from app.infra.agent.types import (
        AgentFieldError,
        CreateAgentItem,
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
    from app.infra.agent.types import AgentFieldError

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

    # --- Active flag resolution ---

    if item.active is not None:
        results = await search_flags(
            conn, redis, search=None,
            flag_type="agent_active",
            limit_count=1000,
        )
        desired = bool(item.active)
        match = next(
            (f for f in results if f.type == "agent_active" and f.value is desired),
            None,
        )
        if match and match.id:
            merged = list(item.flag_ids or [])
            if match.id not in merged:
                merged.append(match.id)
            item.flag_ids = merged
        else:
            errors.append(
                AgentFieldError(
                    field="agent_active",
                    message=f"Flag row not found for agent_active={desired}",
                )
            )

    # --- Cross-artifact artifact ID → *_resource ID resolution ---
    #
    # ``model_id`` / ``tool_ids`` / ``rubric_ids`` supplied by the client are
    # *artifact* IDs (that is what ``/model/search``, ``/tool/search`` and
    # ``/rubric/search`` surface). The agent junctions, however, reference the
    # denormalized ``*_resource`` snapshot each of those artifacts owns via its
    # own self-junction — and the agent read side hydrates them back through
    # the ``*_resource`` getters. ``agent_models_junction`` carries no FK (so a
    # raw artifact ID is a silent broken link), while ``agent_tools_junction``
    # and ``agent_rubrics_junction`` are FK'd to ``tools_resource`` /
    # ``rubrics_resource`` (so a raw artifact ID is a ForeignKeyViolationError
    # → HTTP 500). Resolve artifact IDs to their snapshot resource IDs here.
    # Unknown IDs (e.g. an already-resolved resource ID) pass through.
    if item.model_id is not None:
        model_artifacts = await get_model_artifacts(
            conn, [item.model_id], models=True
        )
        model_map = {
            a.id: a.model_ids[0]
            for a in model_artifacts
            if a.id and a.model_ids
        }
        item.model_id = model_map.get(item.model_id, item.model_id)

    if item.tool_ids:
        tool_artifacts = await get_tool_artifacts(
            conn, list(item.tool_ids), tools=True
        )
        tool_map = {
            a.id: a.tool_ids[0]
            for a in tool_artifacts
            if a.id and a.tool_ids
        }
        item.tool_ids = [tool_map.get(tid, tid) for tid in item.tool_ids]

    # ``rubric_ids`` only exists on CreateAgentItem (UpdateAgentItem has no
    # rubric field), so guard the attribute access for the shared update path.
    item_rubric_ids = getattr(item, "rubric_ids", None)
    if item_rubric_ids:
        rubric_artifacts = await get_rubric_artifacts(
            conn, list(item_rubric_ids), rubrics=True
        )
        rubric_map = {
            a.id: a.rubric_ids[0]
            for a in rubric_artifacts
            if a.id and a.rubric_ids
        }
        # ``rubric_ids`` is only present on CreateAgentItem; ``item_rubric_ids``
        # being truthy implies that branch, so the attribute exists here.
        item.rubric_ids = [  # type: ignore[union-attr]
            rubric_map.get(rid, rid) for rid in item_rubric_ids
        ]

    # Resolve department *artifact* ids -> departments_resource ids before
    # the junction write. ``/department/search`` surfaces artifact ids, but
    # every ``*_departments_junction.departments_id`` is FK'd to
    # ``departments_resource``; writing a raw artifact id violates the FK
    # (HTTP 500). #282 class, missed for the cross-cutting ``department_ids``
    # dimension. Unknown/already-resolved ids pass through. No raw SQL.
    item.department_ids = await resolve_department_ids_to_resource_ids(
        conn, getattr(item, "department_ids", None)
    )

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
        return await get_names(pool, [name_id], redis, bypass_cache=True)

    async def _get_descriptions() -> list:
        if not description_id:
            return []
        return await get_descriptions(pool, [description_id], redis, bypass_cache=True
        )

    async def _get_voices() -> list:
        if not voice_ids:
            return []
        return await get_voices(pool, voice_ids, redis, bypass_cache=True)

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
