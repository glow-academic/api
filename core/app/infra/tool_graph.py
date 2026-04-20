"""Resolve the settings → systems → agents → tools graph.

Given a settings_resource ID, walks the chain using existing black-box
resource fetchers and returns a flat list of resolved tools with full
agent/system context. No raw SQL — purely composes existing functions.

Two public functions:
  resolve_tool_graph()  — async, fetches the chain, returns SettingsToolGraph
  score_tools()         — pure Python, scores/ranks tools for an artifact
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.resources.agents.get import get_agents
from app.tools.resources.agents.types import GetAgentResponse
from app.tools.resources.modalities.get import get_modalities
from app.tools.resources.models.get import get_models
from app.tools.resources.permissions.get import get_permissions
from app.tools.resources.permissions.types import GetPermissionResponse
from app.tools.resources.settings.get import get_settings
from app.tools.resources.systems.get import get_systems
from app.tools.resources.tools.get import get_tools
from app.tools.resources.tools.types import GetToolResponse

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedTool:
    """A single tool fully resolved with its agent and system context."""

    system_id: UUID
    agent_id: UUID
    tool_id: UUID
    operation: str | None  # "create", "link", etc.
    target_type: str  # "resource", "entry", "artifact"
    target: str  # e.g. "names", "contents", "persona"


@dataclass
class SettingsToolGraph:
    """Flat list of resolved tools from a settings chain.

    agent_output_modalities maps agent_id → set of output modality names
    (e.g. {"text", "call", "audio"}), derived from the agent's model's
    modalities_resource entries with is_input=False.
    """

    tools: list[ResolvedTool] = field(default_factory=list)
    agent_output_modalities: dict[UUID, set[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class ScoredTool:
    """A resolved tool with a score for a specific artifact context."""

    tool: ResolvedTool
    coverage: int  # how many artifact resources this agent covers


@dataclass
class ArtifactToolScores:
    """Per-target best tool picks for a given artifact resource set."""

    best: dict[str, ResolvedTool | None]  # target -> best resolved tool
    has_any: dict[str, bool]  # target -> whether any tool exists
    available_modalities: set[str] = field(
        default_factory=set
    )  # union of all agent modalities


# ---------------------------------------------------------------------------
# resolve_tool_graph — async, composes black boxes
# ---------------------------------------------------------------------------


async def resolve_tool_graph(
    pool: asyncpg.Pool,
    settings_id: UUID,
    redis: Redis,
    bypass_cache: bool = False,
) -> SettingsToolGraph:
    """Walk settings → systems → agents → tools and return the flat graph.

    Acquires a single connection for the entire sequential chain.
    """
    async with pool.acquire() as conn:
        return await _resolve_tool_graph_impl(conn, settings_id, redis, bypass_cache)


async def _resolve_tool_graph_impl(
    conn: asyncpg.Connection,
    settings_id: UUID,
    redis: Redis,
    bypass_cache: bool = False,
) -> SettingsToolGraph:
    """Inner implementation — always receives a Connection."""
    # Step 1: settings_resource → system_ids
    settings_list = await get_settings(conn, [settings_id], redis, bypass_cache)
    if not settings_list:
        return SettingsToolGraph()

    setting = settings_list[0]
    system_ids = setting.system_ids or []
    if not system_ids:
        return SettingsToolGraph()

    # Step 2: systems → agent_ids (per system)
    systems = await get_systems(conn, system_ids, redis, bypass_cache)
    if not systems:
        return SettingsToolGraph()

    # Build system_id → agent_ids mapping, collect all unique agent IDs
    system_agent_map: dict[UUID, list[UUID]] = {}
    all_agent_ids: list[UUID] = []
    for system in systems:
        agent_ids = system.agent_ids or []
        system_agent_map[system.id] = agent_ids
        all_agent_ids.extend(agent_ids)

    unique_agent_ids = list(dict.fromkeys(all_agent_ids))
    if not unique_agent_ids:
        return SettingsToolGraph()

    # Step 3: agents → tool_ids (per agent)
    agents = await get_agents(conn, unique_agent_ids, redis, bypass_cache)
    if not agents:
        return SettingsToolGraph()

    agent_by_id: dict[UUID, GetAgentResponse] = {a.id: a for a in agents}

    all_tool_ids: list[UUID] = []
    for agent in agents:
        all_tool_ids.extend(agent.tool_ids or [])

    unique_tool_ids = list(dict.fromkeys(all_tool_ids))
    if not unique_tool_ids:
        return SettingsToolGraph()

    # Step 4: tools → permission_ids
    tools_list = await get_tools(conn, unique_tool_ids, redis, bypass_cache)
    tool_by_id: dict[UUID, GetToolResponse] = {t.id: t for t in tools_list}

    # Collect all unique permission IDs across all tools
    all_permission_ids: list[UUID] = []
    for tool in tools_list:
        all_permission_ids.extend(tool.permission_ids or [])
    unique_permission_ids = list(dict.fromkeys(all_permission_ids))

    # Step 5: resolve permissions → artifact + operation strings
    permission_by_id: dict[UUID, GetPermissionResponse] = {}
    if unique_permission_ids:
        permissions_list = await get_permissions(
            conn, unique_permission_ids, redis, bypass_cache
        )
        permission_by_id = {p.id: p for p in permissions_list}

    # Step 6: resolve agent output modalities from their models
    model_ids = list(dict.fromkeys(
        a.model_id for a in agents if a.model_id is not None
    ))
    modality_by_id: dict[UUID, Any] = {}
    model_by_id: dict[UUID, Any] = {}
    if model_ids:
        models_list = await get_models(conn, model_ids, redis, bypass_cache)
        model_by_id = {m.id: m for m in models_list}

        unique_modality_ids = list(dict.fromkeys(
            mid for m in models_list for mid in (m.modality_ids or [])
        ))
        if unique_modality_ids:
            modalities_list = await get_modalities(
                conn, unique_modality_ids, redis, bypass_cache
            )
            modality_by_id = {m.id: m for m in modalities_list}

    agent_output_modalities: dict[UUID, set[str]] = {}
    for agent in agents:
        mods: set[str] = set()
        model = model_by_id.get(agent.model_id) if agent.model_id else None
        if model:
            for mid in model.modality_ids or []:
                mod = modality_by_id.get(mid)
                if mod and not mod.is_input:
                    mods.add(mod.modality)
        agent_output_modalities[agent.id] = mods

    # Step 7: flatten into ResolvedTool list — one per permission per tool
    resolved: list[ResolvedTool] = []

    for system_id, agent_ids in system_agent_map.items():
        for agent_id in agent_ids:
            agent = agent_by_id.get(agent_id)
            if not agent:
                continue
            for tool_id in agent.tool_ids or []:
                tool = tool_by_id.get(tool_id)
                if not tool:
                    continue
                for perm_id in tool.permission_ids or []:
                    perm = permission_by_id.get(perm_id)
                    if not perm:
                        continue
                    resolved.append(
                        ResolvedTool(
                            system_id=system_id,
                            agent_id=agent_id,
                            tool_id=tool_id,
                            operation=perm.operation,
                            target_type="artifact",
                            target=perm.artifact,
                        )
                    )

    return SettingsToolGraph(
        tools=resolved,
        agent_output_modalities=agent_output_modalities,
    )


# ---------------------------------------------------------------------------
# score_tools — pure Python, no I/O
# ---------------------------------------------------------------------------


def score_tools(
    graph: SettingsToolGraph,
    artifact_resources: set[str],
    modalities: list[str] | None = None,
) -> ArtifactToolScores:
    """Score and pick the winning system + all its agents for a given artifact.

    Scoring:
      1. Only consider tools whose target is in artifact_resources
      2. If modalities specified, hard-filter to systems where ALL agents
         support ALL requested modalities
      3. Pick the system with the best coverage (most artifact_resources covered)
      4. Return ALL agents from the winning system (enables parallel execution + evals)

    Returns the best ResolvedTool per target, has_any flags, and available_modalities.
    """
    if not graph.tools:
        return ArtifactToolScores(
            best=dict.fromkeys(artifact_resources),
            has_any=dict.fromkeys(artifact_resources, False),
            available_modalities=set(),
        )

    # Agent output modalities come from the model (resolved in resolve_tool_graph)
    agent_modalities = graph.agent_output_modalities

    available_modalities = (
        set().union(*agent_modalities.values()) if agent_modalities else set()
    )

    # Group agents by system
    system_agents: dict[UUID, set[UUID]] = {}
    for t in graph.tools:
        system_agents.setdefault(t.system_id, set()).add(t.agent_id)

    # If modalities specified, filter to systems where ALL agents support ALL modalities
    eligible_systems: set[UUID] | None = None
    if modalities:
        required = set(modalities)
        eligible_systems = set()
        for system_id, agent_ids in system_agents.items():
            # At least one agent in the system must support ALL requested modalities
            any_agent_supports = any(
                required <= agent_modalities.get(agent_id, set())
                for agent_id in agent_ids
            )
            if any_agent_supports:
                eligible_systems.add(system_id)

    # Filter tools to eligible systems
    eligible_tools = graph.tools
    if eligible_systems is not None:
        eligible_tools = [t for t in graph.tools if t.system_id in eligible_systems]

    # Compute per-agent coverage and scope from eligible tools
    agent_targets: dict[UUID, set[str]] = {}
    for t in eligible_tools:
        agent_targets.setdefault(t.agent_id, set()).add(t.target)

    agent_coverage: dict[UUID, int] = {
        agent_id: len(targets & artifact_resources)
        for agent_id, targets in agent_targets.items()
    }

    agent_total_scope: dict[UUID, int] = {
        agent_id: len(targets)
        for agent_id, targets in agent_targets.items()
    }

    # For each artifact resource, find the best tool (from eligible systems)
    best: dict[str, ResolvedTool | None] = {}
    has_any: dict[str, bool] = {}

    for resource in artifact_resources:
        candidates = [t for t in eligible_tools if t.target == resource]
        has_any[resource] = len(candidates) > 0

        if not candidates:
            best[resource] = None
            continue

        # Least privilege: narrowest scope, tiebreak by coverage then agent_id
        best[resource] = min(
            candidates,
            key=lambda t: (
                agent_total_scope.get(t.agent_id, 999),
                -agent_coverage.get(t.agent_id, 0),
                t.agent_id,
            ),
        )

    return ArtifactToolScores(
        best=best,
        has_any=has_any,
        available_modalities=available_modalities,
    )
