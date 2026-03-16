"""Shared types for v5 API endpoints.

This module provides reusable type definitions used across multiple artifacts.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.shared_types import (
    QGetAgentsV4Item,
    QGetArgsOutputsV4Item,
    QGetArgsV4Item,
    QGetModelsV4Item,
    QGetProfilesV4Item,
    QGetProvidersV4Item,
    QGetSystemsV4Item,
    QGetToolsV4Item,
)


class BaseResourceSection(BaseModel):
    """Common metadata fields for all resource sections.

    Shared across persona, scenario, simulation, cohort, and other artifacts.
    Uses `tool_id` for create tools and `link_tool_id` for link tools.
    """

    show: bool = Field(False, description="Whether this section is visible in the UI")
    required: bool = Field(False, description="Whether this section requires a selection")
    suggestions: list[UUID] | None = Field(None, description="Suggested resource UUIDs for this section")
    show_ai_generate: bool = Field(False, description="Whether AI generation is available for this section")
    tool_id: UUID | None = Field(None, description="UUID of the create tool for this resource")
    link_tool_id: UUID | None = Field(None, description="UUID of the link tool for this resource")


class ListFilterOption(BaseModel):
    """Standardized option for list endpoint filter sections."""

    id: str | None = Field(None, description="Unique identifier for this filter option")
    name: str | None = Field(None, description="Display name")
    count: int | None = Field(None, description="Number of matching records")
    hex_code: str | None = Field(None, description="Hex color code for display")
    value: str | None = Field(None, description="Internal value")
    type: str | None = Field(None, description="Option type discriminator")


class ListFilterSection(BaseModel):
    """Filter section with options and echoed request state."""

    options: list[ListFilterOption] | None = Field(None, description="Available filter options")
    selected_ids: list[str] | None = Field(None, description="Currently selected filter option IDs")
    search: str | None = Field(None, description="Active search text for filtering")

    @classmethod
    def from_sql_options(
        cls,
        options: list[Any] | None,
        selected_ids: list[UUID] | None,
        search: str | None,
        id_key: str = "value",
        name_key: str = "label",
        count_key: str = "count",
    ) -> "ListFilterSection":
        """Build from SQL option rows (dict or model). Handles value/label/count
        (scenario/simulation/cohort SQL) and id/name/count (persona hydration)."""

        def _get(o: Any, key: str) -> Any:
            return o.get(key) if isinstance(o, dict) else getattr(o, key, None)

        return cls(
            options=[
                ListFilterOption(
                    id=str(_get(o, id_key)) if _get(o, id_key) else None,
                    name=_get(o, name_key),
                    count=_get(o, count_key),
                )
                for o in (options or [])
            ],
            selected_ids=[str(sid) for sid in (selected_ids or [])]
            if selected_ids
            else None,
            search=search,
        )


class DomainAgent(BaseModel):
    """Maps a domain to its assigned agent and group. Used internally by server."""

    domain_id: UUID = Field(..., description="UUID of the domain")
    agent_id: UUID | None = Field(None, description="UUID of the assigned agent")
    group_id: UUID | None = Field(None, description="Per-resource group ID for this domain")


class EntryAgent(BaseModel):
    """Maps an entry_type to its assigned agent and per-entry group."""

    entry_type: str = Field(..., description="Entry type key (e.g. contents, hints, grades, feedbacks)")
    agent_id: UUID | None = Field(None, description="UUID of the assigned agent")
    group_id: UUID | None = Field(None, description="Per-entry group ID")


class DomainData(BaseModel):
    """Rich metadata for a domain, used in generate/regenerate modals."""

    domain_id: UUID = Field(..., description="UUID of the domain")
    name: str = Field(..., description="Display name (e.g. Name, Description, Instructions)")
    description: str = Field(..., description="Description for tooltips and modals")
    resource: str = Field(..., description="Internal resource type identifier")
    icon: str | None = Field(None, description="Optional display icon identifier")
    required: bool = Field(False, description="Whether this domain is required")
    show: bool = Field(True, description="Whether to show this domain in the UI")


class CandidateAgentRow(BaseModel):
    """SQL row type for candidate agent from composite type."""

    agent_id: UUID = Field(..., description="UUID of the agent")
    agent_name: str = Field(..., description="Display name of the agent")
    tool_resources: list[str] | None = Field(None, description="Resource types covered by the agent tools")
    create_tool_ids: list[UUID | None] | None = Field(None, description="Create tool UUIDs per resource")
    link_tool_ids: list[UUID | None] | None = Field(None, description="Link tool UUIDs per resource")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs the agent belongs to")
    updated_at: datetime = Field(..., description="Last updated timestamp")
    is_mcp: bool = Field(False, description="Whether the agent is an MCP agent")


@dataclass
class CandidateAgent:
    """Represents a candidate agent with its tool coverage data for scoring."""

    agent_id: UUID
    agent_name: str
    tool_resources: set[str]
    create_tool_ids: dict[str, UUID]  # resource -> create_tool_id
    link_tool_ids: dict[str, UUID]  # resource -> link_tool_id
    department_ids: set[UUID]
    updated_at: datetime
    is_active: bool
    is_mcp: bool = False

    @classmethod
    def from_sql_row(cls, row: dict) -> "CandidateAgent":
        """Create a CandidateAgent from a SQL row dict."""
        # Build tool_id dicts from parallel arrays
        tool_resources = row["tool_resources"] or []
        create_tool_ids_arr = row.get("create_tool_ids") or []
        link_tool_ids_arr = row.get("link_tool_ids") or []

        create_tool_ids: dict[str, UUID] = {}
        link_tool_ids: dict[str, UUID] = {}

        for i, resource in enumerate(tool_resources):
            if i < len(create_tool_ids_arr) and create_tool_ids_arr[i] is not None:
                create_tool_ids[resource] = create_tool_ids_arr[i]
            if i < len(link_tool_ids_arr) and link_tool_ids_arr[i] is not None:
                link_tool_ids[resource] = link_tool_ids_arr[i]

        return cls(
            agent_id=row["agent_id"],
            agent_name=row["agent_name"],
            tool_resources=set(tool_resources),
            create_tool_ids=create_tool_ids,
            link_tool_ids=link_tool_ids,
            department_ids=set(row["department_ids"] or []),
            updated_at=row["updated_at"],
            is_active=True,
            is_mcp=row["is_mcp"] or False,
        )

    @classmethod
    def from_sql_rows(cls, rows: list[dict] | None) -> list["CandidateAgent"]:
        """Create a list of CandidateAgents from SQL rows."""
        if not rows:
            return []
        return [cls.from_sql_row(row) for row in rows]


def build_domain_data(
    domain_ids: dict[str, UUID | None],
    show_flags: dict[str, bool],
    required_flags: dict[str, bool],
    domain_metadata: dict[str, dict[str, str | bool]],
) -> list[DomainData]:
    """Build rich domain metadata for client display.

    Args:
        domain_ids: Mapping of resource type to domain_id
        show_flags: Mapping of resource type to show flag
        required_flags: Mapping of resource type to required flag
        domain_metadata: Mapping of resource type to display metadata (name, description, icon)

    Returns:
        List of DomainData for client consumption
    """
    result: list[DomainData] = []
    for resource, domain_id in domain_ids.items():
        if domain_id is None:
            continue
        meta = domain_metadata.get(resource, {})
        result.append(
            DomainData(
                domain_id=domain_id,
                name=str(meta.get("name", resource.title())),
                description=str(meta.get("description", "")),
                resource=resource,
                icon=str(meta.get("icon")) if meta.get("icon") else None,
                required=required_flags.get(resource, False),
                show=show_flags.get(resource, True),
            )
        )
    return result


class InternalResponseBase(BaseModel):
    """Base for all internal/websocket fetcher responses. Flat config chain."""

    systems: list[QGetSystemsV4Item] | None = Field(None, description="System configuration items")
    agents: list[QGetAgentsV4Item] | None = Field(None, description="Agent configuration items")
    models: list[QGetModelsV4Item] | None = Field(None, description="Model configuration items")
    providers: list[QGetProvidersV4Item] | None = Field(None, description="Provider configuration items")
    tools: list[QGetToolsV4Item] | None = Field(None, description="Tool configuration items")
    args: list[QGetArgsV4Item] | None = Field(None, description="Argument configuration items")
    args_outputs: list[QGetArgsOutputsV4Item] | None = Field(None, description="Argument output configuration items")
    profile: list[QGetProfilesV4Item] | None = Field(None, description="Profile configuration items")
    params: BaseModel | None = Field(None, description="Additional parameters model")
    resource_system_ids: dict[str, UUID | None] | None = Field(None, description="Mapping of resource type to system UUID")
    resource_agent_ids: dict[str, UUID | None] | None = Field(None, description="Mapping of resource type to agent UUID")
    group_id: UUID | None = Field(None, description="UUID of the owning group")


class FilterOption(BaseModel):
    """A single filter option for dropdown selectors."""

    value: str = Field(..., description="Internal value for the filter option")
    label: str | None = Field(None, description="Display label for the filter option")
    count: int | None = Field(None, description="Number of matching records")


class HistoryItem(BaseModel):
    """Single attempt row in history list."""

    attempt_id: UUID = Field(..., description="UUID of the attempt")
    date: str | None = Field(None, description="Formatted date string of the attempt")
    profile_id: UUID | None = Field(None, description="UUID of the profile who took the attempt")
    profile_name: str | None = Field(None, description="Display name of the profile")
    simulation_id: UUID | None = Field(None, description="UUID of the simulation")
    simulation_name: str | None = Field(None, description="Display name of the simulation")
    num_scenarios: int | None = Field(None, description="Total number of scenarios in the attempt")
    num_scenarios_completed: int | None = Field(None, description="Number of scenarios completed")
    infinite_mode: bool | None = Field(None, description="Whether the attempt is in infinite mode")
    time_limit: int | None = Field(None, description="Time limit in seconds")
    persona_names_junction: list[str] | None = Field(None, description="Persona names from junction table")
    persona_colors_junction: list[str] | None = Field(None, description="Persona colors from junction table")
    scenario_ids: list[UUID] | None = Field(None, description="UUIDs of associated scenarios")
    scenario_titles: list[str] | None = Field(None, description="Titles of associated scenarios")
    department_ids: list[str] | None = Field(None, description="Associated department IDs")
    score: int | None = Field(None, description="Overall attempt score")
    score_status: str | None = Field(None, description="Score status label (e.g. pass, fail)")
    pass_pct: int | None = Field(None, description="Pass percentage threshold")
    show_view: bool | None = Field(None, description="Whether the view action is available")
    show_continue: bool | None = Field(None, description="Whether the continue action is available")
    is_archived: bool | None = Field(None, description="Whether the attempt is archived")
    practice_simulation: bool | None = Field(None, description="Whether this is a practice simulation")
    practice_scenario_id: UUID | None = Field(None, description="UUID of the practice scenario")


class HistoryResponse(BaseModel):
    """Paginated attempt history list."""

    data: list[HistoryItem] = Field(default_factory=list, description="List of history items")
    total_count: int = Field(0, description="Total number of matching records")
    page: int = Field(0, description="Current page number")
    page_size: int = Field(20, description="Items per page")
    total_pages: int = Field(0, description="Total number of pages")
    simulation_options: list[FilterOption] | None = Field(None, description="Filter options for simulations")
    scenario_options: list[FilterOption] | None = Field(None, description="Filter options for scenarios")
    profile_options: list[FilterOption] | None = Field(None, description="Filter options for profiles")


class TestHistoryItem(BaseModel):
    """Single test row in history list."""

    attempt_id: str = Field(..., description="ID of the test attempt")
    eval_id: str | None = Field(None, description="ID of the evaluation")
    eval_name: str | None = Field(None, description="Display name of the evaluation")
    eval_description: str | None = Field(None, description="Description of the evaluation")
    rubric_id: str | None = Field(None, description="ID of the rubric")
    rubric_name: str | None = Field(None, description="Display name of the rubric")
    created_at: str | None = Field(None, description="Creation timestamp string")
    archived: bool = Field(False, description="Whether the test is archived")
    status: str = Field("pending", description="Current test status")
    total_runs: int = Field(0, description="Total number of runs")
    completed_runs: int = Field(0, description="Number of completed runs")
    pending_runs: int = Field(0, description="Number of pending runs")


class TestHistoryResponse(BaseModel):
    """Paginated test history list."""

    data: list[TestHistoryItem] = Field(default_factory=list, description="List of test history items")
    total_count: int = Field(0, description="Total number of matching records")
    page: int = Field(0, description="Current page number")
    page_size: int = Field(10, description="Items per page")
    eval_options: list[FilterOption] | None = Field(None, description="Filter options for evaluations")


class AnalyticsFilterOptions(BaseModel):
    """Filter options returned by analytics endpoints for populating UI dropdowns."""

    earliest_date: str | None = Field(None, description="Earliest date available for filtering")
    simulation_options: list[FilterOption] = Field(default_factory=list, description="Filter options for simulations")
    scenario_options: list[FilterOption] = Field(default_factory=list, description="Filter options for scenarios")
    profile_options: list[FilterOption] = Field(default_factory=list, description="Filter options for profiles")


class BaseAnalyticsRequest(BaseModel):
    """Common request fields shared across analytics endpoints."""

    start_date: str | None = Field(None, description="Start date for the analytics period")
    end_date: str | None = Field(None, description="End date for the analytics period")
    cohort_ids: list[str] = Field(default_factory=list, description="Cohort IDs to filter by")
    department_ids: list[str] = Field(default_factory=list, description="Department IDs to filter by")
    simulation_ids: list[str] = Field(default_factory=list, description="Simulation IDs to filter by")
    roles: list[str] = Field(default_factory=list, description="Roles to filter by")
    simulation_filters: list[str] = Field(default_factory=list, description="Additional simulation filter values")
    actor_profile_id: str | None = Field(None, description="Profile ID of the requesting actor")
    target_profile_id: str | None = Field(None, description="Profile ID of the target user")
