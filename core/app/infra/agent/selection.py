"""Shared permission utilities for v4 API endpoints.

This module provides reusable agent scoring and selection logic
for artifacts that need Python-based agent selection.

For the unified permission model (edit/delete guards, role tiers,
active parent counting), see audits/PERMISSION_UNIFICATION_PLAN.md.
Per-artifact permission logic lives in each artifact's permissions.py.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from app.infra.v5_types import CandidateAgent

if TYPE_CHECKING:
    from app.infra.auth.types import SettingsAgentToolEntry


def resolve_agents_for_artifact(
    entries: list[SettingsAgentToolEntry],
    artifact_types: set[str],
) -> tuple[dict[str, UUID | None], dict[str, UUID | None], dict[str, UUID | None]]:
    """Resolve best agent and tool IDs for each type using settings entries.

    Each SettingsAgentToolEntry has exactly one of resource/entry/artifact set.
    The `type_name` property returns whichever is set. Coverage is computed
    across all three categories uniformly.

    Args:
        entries: Flat agent→tool entries from settings chain.
        artifact_types: Union of resource types, entry types, and artifact types
            needed for this artifact (e.g. {"personas", "contents", "attempt"}).

    Returns:
        (agent_ids, create_tool_ids, link_tool_ids) — all type→UUID|None dicts
    """
    if not entries:
        empty: dict[str, UUID | None] = dict.fromkeys(artifact_types)
        return empty, dict(empty), dict(empty)

    # Group entries by agent: agent_id -> list of entries
    agent_entries: dict[UUID, list[SettingsAgentToolEntry]] = defaultdict(list)
    for e in entries:
        agent_entries[e.agent_id].append(e)

    # Compute coverage per agent (how many artifact types it covers)
    agent_coverage: dict[UUID, int] = {}
    for agent_id, elist in agent_entries.items():
        agent_type_names = {e.type_name for e in elist}
        agent_coverage[agent_id] = len(agent_type_names & artifact_types)

    agent_ids: dict[str, UUID | None] = {}
    create_tool_ids: dict[str, UUID | None] = {}
    link_tool_ids: dict[str, UUID | None] = {}

    for type_name in artifact_types:
        # Find all entries matching this type (across resource/entry/artifact)
        type_entries = [e for e in entries if e.type_name == type_name]
        if not type_entries:
            agent_ids[type_name] = None
            create_tool_ids[type_name] = None
            link_tool_ids[type_name] = None
            continue

        # Pick agent with highest coverage, then by agent_id for determinism
        best_entry = max(
            type_entries,
            key=lambda e: (agent_coverage.get(e.agent_id, 0), e.agent_id),
        )
        agent_ids[type_name] = best_entry.agent_id

        # Find create/link tool IDs for this agent+type
        agent_type_entries = [
            e for e in type_entries if e.agent_id == best_entry.agent_id
        ]
        create_tool_ids[type_name] = next(
            (e.tool_id for e in agent_type_entries if e.is_creatable), None
        )
        link_tool_ids[type_name] = next(
            (e.tool_id for e in agent_type_entries if not e.is_creatable), None
        )

    return agent_ids, create_tool_ids, link_tool_ids


def has_tools_for_resource(
    entries: list[SettingsAgentToolEntry], resource: str
) -> bool:
    """Check if any agent has tools for the given type (resource, entry, or artifact)."""
    return any(e.type_name == resource for e in entries)


def score_agent_for_artifact(
    agent: CandidateAgent,
    artifact_resources: set[str],
    user_department_ids: set[UUID] | None = None,
) -> tuple[int, int, int, datetime, UUID]:
    """Score an agent for a specific artifact context.

    Returns a tuple for sorting (designed so higher values = better agent):
    - matched_artifact_count: How many artifact resources this agent covers
    - negative extra_outside_count: Fewer non-artifact resources = better
    - dept_preference: 0 if matches user department, -1 otherwise
    - updated_at: More recent = better (tiebreaker)
    - agent_id: Final tiebreaker for determinism
    """
    matched_artifact_count = len(agent.tool_resources & artifact_resources)
    extra_outside_count = len(agent.tool_resources - artifact_resources)

    dept_preference = 0
    if user_department_ids and agent.department_ids:
        if not (agent.department_ids & user_department_ids):
            dept_preference = -1

    return (
        matched_artifact_count,
        -extra_outside_count,
        dept_preference,
        agent.updated_at,
        agent.agent_id,
    )


def select_best_agent_for_resource(
    candidates: list[CandidateAgent],
    artifact_resources: set[str],
    target_resource: str,
    user_department_ids: set[UUID] | None = None,
    require_mcp: bool = False,
) -> UUID | None:
    """Select the best agent for a specific resource within an artifact context.

    Scoring criteria (in order of priority):
    1. Must have a tool for the target resource
    2. More tools matching artifact resources = better (specialist)
    3. Fewer tools outside artifact resources = better (not too general)
    4. Matching user department = better
    5. More recently updated = better (tiebreaker)
    """
    eligible = [
        agent
        for agent in candidates
        if agent.is_active
        and target_resource in agent.tool_resources
        and (not require_mcp or agent.is_mcp)
    ]

    if not eligible:
        return None

    scored = sorted(
        eligible,
        key=lambda a: score_agent_for_artifact(
            a, artifact_resources, user_department_ids
        ),
        reverse=True,
    )

    return scored[0].agent_id if scored else None


def select_agents_for_artifact(
    candidates: list[CandidateAgent],
    artifact_resources: set[str],
    resources_needed: list[str],
    user_department_ids: set[UUID] | None = None,
    require_mcp: bool = False,
) -> dict[str, UUID | None]:
    """Select the best agent for each resource in an artifact.

    Returns:
        Dict mapping resource name to best agent ID (or None)
    """
    return {
        resource: select_best_agent_for_resource(
            candidates, artifact_resources, resource, user_department_ids, require_mcp
        )
        for resource in resources_needed
    }


def select_multi_resource_agent(
    candidates: list[CandidateAgent],
    required_resources: set[str],
    artifact_resources: set[str],
    user_department_ids: set[UUID] | None = None,
    require_mcp: bool = False,
) -> UUID | None:
    """Select an agent that has tools for ALL required_resources."""
    eligible = [
        agent
        for agent in candidates
        if agent.is_active
        and required_resources.issubset(agent.tool_resources)
        and (not require_mcp or agent.is_mcp)
    ]

    if not eligible:
        return None

    scored = sorted(
        eligible,
        key=lambda a: score_agent_for_artifact(
            a, artifact_resources, user_department_ids
        ),
        reverse=True,
    )

    return scored[0].agent_id if scored else None
