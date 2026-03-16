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
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.registry.modalities import get_tool_output_modalities
from app.tools.resources.agents.get import get_agents
from app.tools.resources.agents.types import GetAgentResponse
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
    """Flat list of resolved tools from a settings chain."""

    tools: list[ResolvedTool] = field(default_factory=list)


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

    # Step 4: tools → artifact targets
    tools_list = await get_tools(conn, unique_tool_ids, redis, bypass_cache)
    tool_by_id: dict[UUID, GetToolResponse] = {t.id: t for t in tools_list}

    # Step 5: flatten into ResolvedTool list
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
                # Tools currently target artifacts directly in tools_resource.
                for artifact in tool.artifacts or []:
                    resolved.append(
                        ResolvedTool(
                            system_id=system_id,
                            agent_id=agent_id,
                            tool_id=tool_id,
                            operation=tool.operation,
                            target_type="artifact",
                            target=artifact,
                        )
                    )

    return SettingsToolGraph(tools=resolved)


# ---------------------------------------------------------------------------
# score_tools — pure Python, no I/O
# ---------------------------------------------------------------------------


def score_tools(
    graph: SettingsToolGraph,
    artifact_resources: set[str],
    modality: str | None = None,
) -> ArtifactToolScores:
    """Score and pick the best tool per target for a given artifact.

    Scoring (per target):
      1. Only consider tools whose target is in artifact_resources
      2. Per agent, compute coverage = how many artifact_resources it covers
      3. If modality specified, hard-filter to agents supporting that modality
      4. Pick the agent with highest coverage (specialist wins)
      5. Deterministic tiebreak by agent_id

    Returns the best ResolvedTool per target, has_any flags, and available_modalities.
    """
    if not graph.tools:
        return ArtifactToolScores(
            best=dict.fromkeys(artifact_resources),
            has_any=dict.fromkeys(artifact_resources, False),
            available_modalities=set(),
        )

    # Group resolved tools by (agent_id, tool_id) to reconstruct per-tool target lists
    tool_groups: dict[tuple[UUID, UUID], list[ResolvedTool]] = {}
    for t in graph.tools:
        tool_groups.setdefault((t.agent_id, t.tool_id), []).append(t)

    # Compute per-agent modalities from their tools
    agent_modalities: dict[UUID, set[str]] = {}
    for (agent_id, _tool_id), tools in tool_groups.items():
        resources = [t.target for t in tools if t.target_type == "resource"]
        entries = [t.target for t in tools if t.target_type == "entry"]
        artifacts = [t.target for t in tools if t.target_type == "artifact"]
        operation = tools[0].operation
        tool_mods = get_tool_output_modalities(operation, resources, entries, artifacts)
        agent_modalities.setdefault(agent_id, set()).update(tool_mods)

    available_modalities = (
        set().union(*agent_modalities.values()) if agent_modalities else set()
    )

    # Compute per-agent coverage: how many artifact_resources does each agent touch?
    agent_targets: dict[UUID, set[str]] = {}
    for t in graph.tools:
        agent_targets.setdefault(t.agent_id, set()).add(t.target)

    agent_coverage: dict[UUID, int] = {
        agent_id: len(targets & artifact_resources)
        for agent_id, targets in agent_targets.items()
    }

    # If modality specified, determine which agents support it
    eligible_agents: set[UUID] | None = None
    if modality is not None:
        eligible_agents = {
            agent_id for agent_id, mods in agent_modalities.items() if modality in mods
        }

    # For each artifact resource, find the best tool
    best: dict[str, ResolvedTool | None] = {}
    has_any: dict[str, bool] = {}

    for resource in artifact_resources:
        candidates = [t for t in graph.tools if t.target == resource]
        has_any[resource] = len(candidates) > 0

        if not candidates:
            best[resource] = None
            continue

        # Apply modality filter if specified
        if eligible_agents is not None:
            candidates = [t for t in candidates if t.agent_id in eligible_agents]

        if not candidates:
            best[resource] = None
            continue

        # Pick by: highest coverage, then agent_id for determinism
        best[resource] = max(
            candidates,
            key=lambda t: (agent_coverage.get(t.agent_id, 0), t.agent_id),
        )

    return ArtifactToolScores(
        best=best,
        has_any=has_any,
        available_modalities=available_modalities,
    )
