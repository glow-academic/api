"""Handcrafted types for agent endpoints (section-first contracts)."""

from __future__ import annotations

import datetime as dt
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.agent.create import CreateAgentItem
from app.infra.v5_types import BaseResourceSection, ListFilterSection
from app.tools.entries.agent_drafts.types import GetAgentDraftResponse


class AgentFlagConfig(BaseModel):
    """Enriched flag config for direct client consumption."""

    key: str = Field(..., description="Flag config key identifier")
    label: str = Field(..., description="Display label for the flag")
    description: str | None = Field(None, description="Flag description text")
    icon_id: str | None = Field(None, description="UUID of the selected icon resource")
    flag_option_id: UUID | None = Field(None, description="UUID of the flag option")
    show: bool = Field(True, description="Whether to show this flag in the UI")
    required: bool = Field(False, description="Whether this flag is required")
    generated: bool | None = Field(None, description="Whether this was AI-generated")


class AgentNameSection(BaseResourceSection):
    resource: Any | None = Field(None, description="Currently selected name resource")
    resources: list[Any] | None = Field(None, description="Available name resources")


class AgentDescriptionSection(BaseResourceSection):
    resource: Any | None = Field(None, description="Currently selected description resource")
    resources: list[Any] | None = Field(None, description="Available description resources")


class AgentModelSection(BaseResourceSection):
    resource: Any | None = Field(None, description="Currently selected model resource")
    resources: list[Any] | None = Field(None, description="Available model resources")


class AgentPromptSection(BaseResourceSection):
    resource: Any | None = Field(None, description="Currently selected prompt resource")
    resources: list[Any] | None = Field(None, description="Available prompt resources")


class AgentInstructionSection(BaseResourceSection):
    resource: Any | None = Field(None, description="Currently selected instruction resource")
    resources: list[Any] | None = Field(None, description="Available instruction resources")


class AgentFlagSection(BaseResourceSection):
    current: list[AgentFlagConfig] | None = Field(None, description="Currently selected flags")
    resources: list[AgentFlagConfig] | None = Field(None, description="Available flag configs")


class AgentDepartmentSection(BaseResourceSection):
    current: list[Any] | None = Field(None, description="Currently selected departments")
    resources: list[Any] | None = Field(None, description="Available department resources")


class AgentToolSection(BaseResourceSection):
    current: list[Any] | None = Field(None, description="Currently selected tools")
    resources: list[Any] | None = Field(None, description="Available tool resources")


class AgentTemperatureLevelSection(BaseResourceSection):
    resource: Any | None = Field(None, description="Currently selected temperature level")
    resources: list[Any] | None = Field(None, description="Available temperature levels")


class AgentReasoningLevelSection(BaseResourceSection):
    resource: Any | None = Field(None, description="Currently selected reasoning level")
    resources: list[Any] | None = Field(None, description="Available reasoning levels")


class AgentVoiceSection(BaseResourceSection):
    current: list[Any] | None = Field(None, description="Currently selected voices")
    resources: list[Any] | None = Field(None, description="Available voice resources")


class AgentQualitySection(BaseResourceSection):
    current: list[Any] | None = Field(None, description="Currently selected qualities")
    resources: list[Any] | None = Field(None, description="Available quality resources")


class AgentRubricSection(BaseResourceSection):
    current: list[Any] | None = Field(None, description="Currently selected rubrics")
    resources: list[Any] | None = Field(None, description="Available rubric resources")


class GetAgentApiRequest(BaseModel):
    """Request model for get agent endpoint."""

    agent_id: UUID | None = Field(None, description="UUID of the agent to retrieve")
    draft_id: UUID | None = Field(None, description="UUID of the draft to retrieve")


class GetAgentApiResponse(BaseModel):
    """Section-first response model for get agent endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    agent_exists: bool | None = Field(None, description="Whether the agent exists")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    disabled_reason: str | None = Field(None, description="Reason the agent is disabled")
    draft_version: int | None = Field(None, description="Current draft version number")
    group_id: UUID | None = Field(None, description="UUID of the owning group")

    basic_show_ai_generate: bool | None = Field(None, description="Show AI generate for basic step")
    general_show_ai_generate: bool | None = Field(None, description="Show AI generate for general step")

    names: AgentNameSection | None = Field(None, description="Name section data")
    descriptions: AgentDescriptionSection | None = Field(None, description="Description section data")
    models: AgentModelSection | None = Field(None, description="Model section data")
    prompts: AgentPromptSection | None = Field(None, description="Prompt section data")
    instructions: AgentInstructionSection | None = Field(None, description="Instruction section data")
    flags: AgentFlagSection | None = Field(None, description="Flag section data")
    departments: AgentDepartmentSection | None = Field(None, description="Department section data")
    tools: AgentToolSection | None = Field(None, description="Tool section data")
    temperature_levels: AgentTemperatureLevelSection | None = Field(None, description="Temperature level section data")
    reasoning_levels: AgentReasoningLevelSection | None = Field(None, description="Reasoning level section data")
    voices: AgentVoiceSection | None = Field(None, description="Voice section data")
    qualities: AgentQualitySection | None = Field(None, description="Quality section data")
    rubrics: AgentRubricSection | None = Field(None, description="Rubric section data")


# ========== Shared Create/Update Types ==========


class AgentFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field with the error")
    message: str = Field(..., description="Human-readable error message")


class AgentResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    agent_id: UUID | None = Field(None, description="UUID of the affected agent")
    message: str = Field(..., description="Human-readable result message")
    errors: list[AgentFieldError] | None = Field(None, description="List of per-field errors")


# ========== Create Endpoint Types ==========


class CreateAgentApiRequest(BaseModel):
    """Request model for bulk create agent endpoint."""

    agents: list[CreateAgentItem] = Field(..., description="List of agents to create")


class CreateAgentApiResponse(BaseModel):
    """Response model for bulk create agent endpoint."""

    results: list[AgentResultItem] = Field(..., description="List of operation results")


# ========== Update Endpoint Types ==========


class UpdateAgentItem(BaseModel):
    """Single agent item for update — agent_id required, all fields optional."""

    agent_id: UUID = Field(..., description="UUID of the agent to update")
    # Dual-mode: name
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Display name value")
    # Dual-mode: description
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description text value")
    # Dual-mode: departments (match by name)
    department_ids: list[UUID] | None = Field(None, description="Associated department UUIDs")
    departments: list[str] | None = Field(None, description="Department names for matching")
    # ID-only fields
    flag_ids: list[UUID] | None = Field(None, description="Associated flag UUIDs")
    model_ids: list[UUID] | None = Field(None, description="Associated model UUIDs")
    reasoning_level_ids: list[UUID] | None = Field(None, description="Associated reasoning level UUIDs")
    temperature_level_ids: list[UUID] | None = Field(None, description="Associated temperature level UUIDs")
    tool_ids: list[UUID] | None = Field(None, description="Associated tool UUIDs")
    voice_ids: list[UUID] | None = Field(None, description="Associated voice UUIDs")
    agent_ids: list[UUID] | None = Field(None, description="Associated agent resource UUIDs")


class UpdateAgentApiRequest(BaseModel):
    """Request model for bulk update agent endpoint."""

    agents: list[UpdateAgentItem] = Field(..., description="List of agents to update")


class UpdateAgentApiResponse(BaseModel):
    """Response model for bulk update agent endpoint."""

    results: list[AgentResultItem] = Field(..., description="List of operation results")


class SaveAgentFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field with the error")
    message: str = Field(..., description="Human-readable error message")


class DeleteAgentApiRequest(BaseModel):
    """Request model for bulk delete agent endpoint."""

    agent_ids: list[UUID] = Field(..., description="UUIDs of agents to delete")


class DeleteAgentResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    agent_id: UUID = Field(..., description="UUID of the deleted agent")
    message: str = Field(..., description="Human-readable result message")


class DeleteAgentApiResponse(BaseModel):
    """Response model for bulk delete agent endpoint."""

    results: list[DeleteAgentResult] = Field(..., description="List of operation results")


class DuplicateAgentApiRequest(BaseModel):
    """Request model for duplicate agent endpoint."""

    agent_id: UUID = Field(..., description="UUID of the agent to duplicate")


class DuplicateAgentApiResponse(BaseModel):
    """Response model for duplicate agent endpoint."""

    success: bool = Field(..., description="Whether the operation succeeded")
    agent_id: UUID = Field(..., description="UUID of the duplicated agent")
    message: str = Field(..., description="Human-readable result message")


class PatchAgentDraftApiRequest(BaseModel):
    """Request model for new-style agent draft endpoint.

    Dual-mode for creatable resources only:
      - name/name_id, description/description_id
    ID-only for non-creatable resources:
      - flag_ids, department_ids, model_ids, tool_ids, reasoning_level_ids,
        temperature_level_ids, voice_ids, rubric_ids

    Client always sends full state (append-only — each write is a new version snapshot).
    """

    group_id: UUID | None = Field(None, description="UUID of the owning group")
    input_draft_id: UUID | None = Field(None, description="UUID of the input draft")
    expected_version: int = Field(0, description="Expected draft version for optimistic lock")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, description="Display name value")
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    description: str | None = Field(None, description="Description text value")
    description_id: UUID | None = Field(None, description="UUID of the description resource")

    # Non-creatable — ID-only
    flag_ids: list[UUID] | None = Field(None, description="Associated flag UUIDs")
    department_ids: list[UUID] | None = Field(None, description="Associated department UUIDs")
    model_ids: list[UUID] | None = Field(None, description="Associated model UUIDs")
    tool_ids: list[UUID] | None = Field(None, description="Associated tool UUIDs")
    reasoning_level_ids: list[UUID] | None = Field(None, description="Associated reasoning level UUIDs")
    temperature_level_ids: list[UUID] | None = Field(None, description="Associated temperature level UUIDs")
    voice_ids: list[UUID] | None = Field(None, description="Associated voice UUIDs")
    rubric_ids: list[UUID] | None = Field(None, description="Associated rubric UUIDs")


class AgentDraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="UUID of the selected name resource")
    description_id: UUID | None = Field(None, description="UUID of the selected description resource")
    flag_ids: list[UUID] = Field(..., description="Selected flag UUIDs")
    department_ids: list[UUID] = Field(..., description="Selected department UUIDs")
    model_ids: list[UUID] = Field(..., description="Selected model UUIDs")
    tool_ids: list[UUID] = Field(..., description="Selected tool UUIDs")
    reasoning_level_ids: list[UUID] = Field(..., description="Selected reasoning level UUIDs")
    temperature_level_ids: list[UUID] = Field(..., description="Selected temperature level UUIDs")
    voice_ids: list[UUID] = Field(..., description="Selected voice UUIDs")
    rubric_ids: list[UUID] = Field(..., description="Selected rubric UUIDs")


class PatchAgentDraftApiResponse(BaseModel):
    """Response model for new-style agent draft endpoint."""

    success: bool = Field(..., description="Whether the operation succeeded")
    draft_id: UUID = Field(..., description="UUID of the saved draft")
    new_version: int = Field(..., description="New draft version number")
    message: str = Field(..., description="Human-readable result message")
    form_state: AgentDraftFormState | None = Field(None, description="Server-authoritative form state")


class GetAgentDraftsApiResponse(BaseModel):
    """Response model for agent drafts list endpoint."""

    entries: list[GetAgentDraftResponse] | None = Field(None, description="List of agent draft entries")


# ========== List Endpoint Types ==========


# ========== Export Endpoint Types ==========


class ExportAgentApiRequest(BaseModel):
    """Request model for export agent endpoint."""

    agent_id: UUID | None = Field(None, description="UUID of the agent to export")


class ExportAgentApiResponse(BaseModel):
    """Response model for export agent endpoint."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Suggested file name for download")
    mime_type: str = Field(..., description="MIME type of the exported content")
    row_count: int = Field(..., description="Total number of exported rows")


class ListAgentApiAgent(BaseModel):
    """Agent type for list endpoint with computed permissions."""

    agent_id: UUID | None = Field(None, description="UUID of the agent")
    name: str | None = Field(None, description="Display name")
    description: str | None = Field(None, description="Agent description text")
    reasoning: str | None = Field(None, description="Reasoning level label")
    temperature: float | None = Field(None, description="Temperature setting value")
    model_id: UUID | None = Field(None, description="UUID of the selected model")
    model_name: str | None = Field(None, description="Display name of the model")
    model_description: str | None = Field(None, description="Description of the model")
    role: str | None = Field(None, description="Agent role identifier")
    updated_at: dt.datetime | None = Field(None, description="Last updated timestamp")
    department_ids: list[str] | None = Field(None, description="Associated department UUIDs")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    can_duplicate: bool | None = Field(None, description="Whether the current user can duplicate")
    can_delete: bool | None = Field(None, description="Whether the current user can delete")


class ListAgentApiResponse(BaseModel):
    """Response model for list agent endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    agents: list[ListAgentApiAgent] | None = Field(None, description="List of agent items")
    department_filter: ListFilterSection | None = Field(None, description="Filter options for departments")
    model_filter: ListFilterSection | None = Field(None, description="Filter options for models")
    tool_filter: ListFilterSection | None = Field(None, description="Filter options for tools")
    total_count: int | None = Field(None, description="Total number of matching records")
