"""Handcrafted types for agent endpoints."""

from __future__ import annotations

import datetime as dt
from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.api_types import ListFilterSection
from app.infra.persona.types import ImportField
from app.infra.resource_type_filter import ScopedItem
from app.tools.entries.agent_drafts.types import GetAgentDraftResponse


class AgentFlagResource(BaseModel):
    """Flag option row — one per (name, type, value) entry in flags_resource."""

    id: UUID | None = Field(None, description="Flag resource identifier")
    name: str | None = Field(None, description="Flag display name")
    type: str | None = Field(None, description="Flag type (e.g. 'agent_active')")
    value: bool | None = Field(None, description="Underlying bool value of this option")
    description: str | None = Field(None, description="Flag description text")
    icon_id: UUID | None = Field(None, description="UUID of the selected icon resource")
    icon: str | None = Field(None, description="Resolved SVG markup for the icon (hydrated from icons_resource)")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class AgentNameResource(BaseModel):
    id: UUID | None = Field(None, description="Name resource identifier")
    name: str | None = Field(None, description="Agent name")
    generated: bool | None = Field(None, description="Whether the name was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class AgentDescriptionResource(BaseModel):
    id: UUID | None = Field(None, description="Description resource identifier")
    description: str | None = Field(None, description="Agent description")
    generated: bool | None = Field(None, description="Whether the description was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class AgentModelResource(BaseModel):
    id: UUID | None = Field(None, description="Model resource identifier")
    name: str | None = Field(None, description="Model name")
    description: str | None = Field(None, description="Model description")
    value: str | None = Field(None, description="Model value")
    provider_id: UUID | None = Field(None, description="Provider identifier")
    department_ids: list[UUID] | None = Field(None, description="Associated department identifiers")
    temperature_level_ids: list[UUID] | None = Field(None, description="Associated temperature level identifiers")
    reasoning_level_ids: list[UUID] | None = Field(None, description="Associated reasoning level identifiers")
    quality_ids: list[UUID] | None = Field(None, description="Associated quality identifiers")
    voice_ids: list[UUID] | None = Field(None, description="Associated voice identifiers")
    modality_ids: list[UUID] | None = Field(None, description="Associated modality identifiers")
    generated: bool | None = Field(None, description="Whether the model was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class AgentPromptResource(BaseModel):
    id: UUID | None = Field(None, description="Prompt resource identifier")
    system_prompt: str | None = Field(None, description="Prompt system text")
    name: str | None = Field(None, description="Prompt name")
    description: str | None = Field(None, description="Prompt description")
    generated: bool | None = Field(None, description="Whether the prompt was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class AgentInstructionResource(BaseModel):
    id: UUID | None = Field(None, description="Instruction resource identifier")
    template: str | None = Field(None, description="Instruction template")
    generated: bool | None = Field(None, description="Whether the instruction was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class AgentDepartmentResource(BaseModel):
    department_id: UUID | None = Field(None, description="Department identifier")
    name: str | None = Field(None, description="Department name")
    description: str | None = Field(None, description="Department description")
    generated: bool | None = Field(None, description="Whether the department was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class AgentToolResource(BaseModel):
    id: UUID | None = Field(None, description="Tool resource identifier")
    name: str | None = Field(None, description="Tool name")
    description: str | None = Field(None, description="Tool description")
    permission_ids: list[UUID] | None = Field(None, description="Associated permission identifiers")
    department_ids: list[UUID] | None = Field(None, description="Associated department identifiers")
    args_ids: list[UUID] | None = Field(None, description="Associated arg identifiers")
    args_output_ids: list[UUID] | None = Field(None, description="Associated arg output identifiers")
    instruction_id: UUID | None = Field(None, description="Associated instruction identifier")
    agent_id: UUID | None = Field(None, description="Associated denormalized agent identifier")
    generated: bool | None = Field(None, description="Whether the tool was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class AgentTemperatureLevelResource(BaseModel):
    id: UUID | None = Field(None, description="Temperature level resource identifier")
    temperature: float | None = Field(None, description="Temperature value")
    generated: bool | None = Field(None, description="Whether the temperature level was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class AgentReasoningLevelResource(BaseModel):
    id: UUID | None = Field(None, description="Reasoning level resource identifier")
    reasoning_level: str | None = Field(None, description="Reasoning level value")
    generated: bool | None = Field(None, description="Whether the reasoning level was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class AgentVoiceResource(BaseModel):
    id: UUID | None = Field(None, description="Voice resource identifier")
    voice: str | None = Field(None, description="Voice value")
    generated: bool | None = Field(None, description="Whether the voice was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class AgentQualityResource(BaseModel):
    id: UUID | None = Field(None, description="Quality resource identifier")
    quality: str | None = Field(None, description="Quality value")
    generated: bool | None = Field(None, description="Whether the quality was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class AgentRubricResource(BaseModel):
    id: UUID | None = Field(None, description="Rubric resource identifier")
    name: str | None = Field(None, description="Rubric name")
    description: str | None = Field(None, description="Rubric description")
    department_ids: list[UUID] | None = Field(None, description="Associated department identifiers")
    total_points: int | None = Field(None, description="Total points")
    pass_points: int | None = Field(None, description="Passing points")
    simulation_rubric: bool | None = Field(None, description="Whether this rubric is for simulation")
    video_rubric: bool | None = Field(None, description="Whether this rubric is for video")
    standard_group_ids: list[UUID] | None = Field(None, description="Associated standard group identifiers")
    generated: bool | None = Field(None, description="Whether the rubric was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class SectionFilter(BaseModel):
    search: str | None = Field(None, description="Filter options by search text")
    limit: int | None = Field(None, description="Max options to return")
    selected: bool | None = Field(None, description="Only return selected items")
    suggested: bool | None = Field(None, description="Only return suggested items")
    include: bool | None = Field(None, description="Include this section in response (default true)")


class GetAgentApiRequest(BaseModel):
    """Request model for get agent endpoint."""

    id: UUID | None = Field(None, description="UUID of the agent to retrieve")
    agent_id: UUID | None = Field(None, description="Legacy alias for the agent identifier")
    draft_id: UUID | None = Field(None, description="UUID of the draft to retrieve")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")
    names: SectionFilter | None = Field(None, description="Filter options for names")
    descriptions: SectionFilter | None = Field(None, description="Filter options for descriptions")
    models: SectionFilter | None = Field(None, description="Filter options for models")
    prompts: SectionFilter | None = Field(None, description="Filter options for prompts")
    instructions: SectionFilter | None = Field(None, description="Filter options for instructions")
    flags: SectionFilter | None = Field(None, description="Filter options for flags")
    departments: SectionFilter | None = Field(None, description="Filter options for departments")
    tools: SectionFilter | None = Field(None, description="Filter options for tools")
    temperature_levels: SectionFilter | None = Field(None, description="Filter options for temperature levels")
    reasoning_levels: SectionFilter | None = Field(None, description="Filter options for reasoning levels")
    voices: SectionFilter | None = Field(None, description="Filter options for voices")
    qualities: SectionFilter | None = Field(None, description="Filter options for qualities")
    rubrics: SectionFilter | None = Field(None, description="Filter options for rubrics")


class GetAgentApiResponse(BaseModel):
    """Canonical composed response model for get agent endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    agent_exists: bool | None = Field(None, description="Whether the agent exists")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    disabled_reason: str | None = Field(None, description="Reason the agent is disabled")
    group_id: UUID | None = Field(None, description="UUID of the owning group")
    draft_name: str | None = Field(
        None,
        description="Immutable draft label from the active draft entry, when a "
        "``draft_id`` was supplied. ``None`` for non-draft fetches.",
    )
    agent_id: UUID | None = Field(None, description="UUID of the selected agent")
    show_ai_generate: bool | None = Field(None, description="Whether any step should show AI generate")
    basic_show_ai_generate: bool | None = Field(None, description="Show AI generate for basic step")
    general_show_ai_generate: bool | None = Field(None, description="Show AI generate for general step")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource identifiers when available")

    names: list[AgentNameResource] | None = Field(None, description="Name resources")
    descriptions: list[AgentDescriptionResource] | None = Field(None, description="Description resources")
    models: list[AgentModelResource] | None = Field(None, description="Model resources")
    prompts: list[AgentPromptResource] | None = Field(None, description="Prompt resources")
    instructions: list[AgentInstructionResource] | None = Field(None, description="Instruction resources")
    flags: list[AgentFlagResource] | None = Field(None, description="Flag resources (one per flags_resource row, value=true/false)")
    departments: list[AgentDepartmentResource] | None = Field(None, description="Department resources")
    tools: list[AgentToolResource] | None = Field(None, description="Tool resources")
    temperature_levels: list[AgentTemperatureLevelResource] | None = Field(None, description="Temperature level resources")
    reasoning_levels: list[AgentReasoningLevelResource] | None = Field(None, description="Reasoning level resources")
    voices: list[AgentVoiceResource] | None = Field(None, description="Voice resources")
    qualities: list[AgentQualityResource] | None = Field(None, description="Quality resources")
    rubrics: list[AgentRubricResource] | None = Field(None, description="Rubric resources")


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


class CreateAgentItem(ScopedItem):
    """Single agent item for create — no agent_id.

    Required fields (name): provide ID or value.
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name_id": "names",
        "name": "names",
        "description_id": "descriptions",
        "description": "descriptions",
        "department_ids": "departments",
        "departments": "departments",
        "flag_ids": "flags",
        "model_id": "models",
        "reasoning_level_ids": "reasoning_levels",
        "temperature_level_ids": "temperature_levels",
        "tool_ids": "tools",
        "voice_ids": "voices",
        "agent_ids": "agents",
    }

    id: UUID | None = Field(None, description="Client-provided UUID for the agent")
    resource_id: UUID | None = Field(None, description="Optional preset UUID for the resource snapshot")

    # Dual-mode: name
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Display name value")
    # Dual-mode: description
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description text value")
    # Dual-mode: departments (match by name)
    department_ids: list[UUID] | None = Field(None, description="Associated department UUIDs")
    departments: list[str] | None = Field(None, description="Department names for matching")
    # Canonical flag ids + denormalized bool
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs")
    active: bool | None = Field(None, description="Denormalized agent_active flag state")
    model_id: UUID | None = Field(None, description="Associated model UUID")
    reasoning_level_ids: list[UUID] | None = Field(None, description="Associated reasoning level UUIDs")
    temperature_level_ids: list[UUID] | None = Field(None, description="Associated temperature level UUIDs")
    tool_ids: list[UUID] | None = Field(None, description="Associated tool UUIDs")
    voice_ids: list[UUID] | None = Field(None, description="Associated voice UUIDs")
    agent_ids: list[UUID] | None = Field(None, description="Associated agent resource UUIDs")
    rubric_ids: list[UUID] | None = Field(None, description="Associated rubric UUIDs")
    prompt_id: UUID | None = Field(None, description="System prompt resource UUID")
    instruction_ids: list[UUID] | None = Field(None, description="Instruction template resource UUIDs")


class CreateAgentApiRequest(BaseModel):
    """Request model for bulk create agent endpoint."""

    agents: list[CreateAgentItem] | None = Field(None, description="List of agents to create (omit on the ack call)")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant create")
    soft: bool = Field(False, description="Stage the create dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class CreateAgentApiResponse(BaseModel):
    """Response model for bulk create agent endpoint."""

    results: list[AgentResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# ========== Update Endpoint Types ==========


class UpdateAgentItem(ScopedItem):
    """Single agent item for update — agent_id required, all fields optional."""

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = CreateAgentItem.RESOURCE_TYPE_MAP

    id: UUID = Field(..., description="UUID of the agent to update")
    # Dual-mode: name
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Display name value")
    # Dual-mode: description
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description text value")
    # Dual-mode: departments (match by name)
    department_ids: list[UUID] | None = Field(None, description="Associated department UUIDs")
    departments: list[str] | None = Field(None, description="Department names for matching")
    # Canonical flag ids + denormalized bool
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs")
    active: bool | None = Field(None, description="Denormalized agent_active flag state")
    model_id: UUID | None = Field(None, description="Associated model UUID")
    reasoning_level_ids: list[UUID] | None = Field(None, description="Associated reasoning level UUIDs")
    temperature_level_ids: list[UUID] | None = Field(None, description="Associated temperature level UUIDs")
    tool_ids: list[UUID] | None = Field(None, description="Associated tool UUIDs")
    voice_ids: list[UUID] | None = Field(None, description="Associated voice UUIDs")
    agent_ids: list[UUID] | None = Field(None, description="Associated agent resource UUIDs")


class UpdateAgentPatch(UpdateAgentItem):
    """Shared patch for bulk-update-all-matching mode.

    Inherits every field from ``UpdateAgentItem`` and just relaxes
    ``id`` to optional — the bulk impl stamps the resolved id onto a
    clone of the patch per matched row, so any client-supplied id is
    ignored. Sparse semantics: only fields the client sets are written.
    """

    id: UUID | None = Field(  # type: ignore[assignment]
        None,
        description="Ignored — bulk impl stamps the resolved agent id per matched row",
    )


class UpdateAgentApiRequest(BaseModel):
    """Request model for bulk update agent endpoint.

    Three body shapes:
      - First call (explicit): ``agents`` required — per-row patches.
      - First call (all-matching): ``all=true`` plus the filter fields
        ``/agent/search`` accepts plus a single shared ``patch`` that
        every matched row receives. The impl resolves matching ids,
        subtracts ``excluded_ids``, and runs the existing per-row
        update flow with the patch cloned per id.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant update by ``idempotency_key``.
    """

    agents: list[UpdateAgentItem] | None = Field(
        None, description="List of agents to update (required on first call when ``all`` is false)",
    )

    # All-matching path. Same shape as DeleteAgentApiRequest; ``patch``
    # is the shared change set applied to every matched row. ``patch.id``
    # is ignored — each resolved id is stamped onto a clone before the
    # per-row update fires.
    all: bool | None = Field(False, description="When true, apply ``patch`` to every agent matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    patch: UpdateAgentPatch | None = Field(None, description="Shared change set applied to every matched row when ``all=true`` (sparse — only set fields are updated; ``patch.id`` ignored)")
    search: str | None = Field(None, description="Full-text search query")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    filter_model_ids: list[UUID] | None = Field(None, description="Filter by model UUIDs")
    filter_tool_ids: list[UUID] | None = Field(None, description="Filter by tool UUIDs")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    model_search: str | None = Field(None, description="Search text for model facet (no-op for row filtering)")
    tool_search: str | None = Field(None, description="Search text for tool facet (no-op for row filtering)")
    flag_search: str | None = Field(None, description="Search text for flag facet (no-op for row filtering)")

    # Ack
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant update")
    soft: bool = Field(False, description="Stage the update dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class UpdateAgentApiResponse(BaseModel):
    """Response model for bulk update agent endpoint."""

    results: list[AgentResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class SaveAgentFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field with the error")
    message: str = Field(..., description="Human-readable error message")


class DeleteAgentApiRequest(BaseModel):
    """Request model for bulk delete agent endpoint.

    Three body shapes:
      - First call (explicit): ``agent_ids`` required.
      - First call (all-matching): ``all=true`` plus the same filter
        fields ``/agent/search`` accepts. The impl resolves every
        matching id server-side, subtracts ``excluded_ids``, and runs
        the existing per-row delete flow.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant deletion by ``idempotency_key``.
    """

    agent_ids: list[UUID] | None = Field(
        None, description="UUIDs of agents to delete (required on first call when ``all`` is false)",
    )

    # All-matching path. Field names mirror ``SearchAgentApiRequest``
    # so the client can pass URL-backed nuqs filter state through to a
    # bulk delete unchanged. Independent class (not a shared "filter"
    # sub-model) so future divergence from search predicates is trivial.
    all: bool | None = Field(False, description="When true, delete every agent matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    # Filter fields (same shape as /agent/search). Only meaningful
    # when ``all=true``; the validator does not enforce that today —
    # the impl simply ignores them when ``agent_ids`` is set.
    search: str | None = Field(None, description="Full-text search query")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    filter_model_ids: list[UUID] | None = Field(None, description="Filter by model UUIDs")
    filter_tool_ids: list[UUID] | None = Field(None, description="Filter by tool UUIDs")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    model_search: str | None = Field(None, description="Search text for model facet (no-op for row filtering)")
    tool_search: str | None = Field(None, description="Search text for tool facet (no-op for row filtering)")
    flag_search: str | None = Field(None, description="Search text for flag facet (no-op for row filtering)")

    # Ack
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — confirms or rejects a dormant delete")
    soft: bool = Field(False, description="Stage the delete dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (confirm) or reject dormant state. Only meaningful with idempotency_key")


class DeleteAgentResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    agent_id: UUID = Field(..., description="UUID of the deleted agent")
    message: str = Field(..., description="Human-readable result message")


class DeleteAgentApiResponse(BaseModel):
    """Response model for bulk delete agent endpoint."""

    results: list[DeleteAgentResult] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class DuplicateAgentApiRequest(BaseModel):
    """Request model for duplicate agent endpoint."""

    agent_id: UUID = Field(..., description="UUID of the agent to duplicate")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant duplicate")
    soft: bool = Field(False, description="Stage the duplicate dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DuplicateAgentApiResponse(BaseModel):
    """Response model for duplicate agent endpoint."""

    success: bool = Field(..., description="Whether the operation succeeded")
    agent_id: UUID = Field(..., description="UUID of the duplicated agent")
    message: str = Field(..., description="Human-readable result message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


class CreatePromptInput(BaseModel):
    """Inline prompt creation input."""
    system_prompt: str = Field(..., description="System prompt text")
    name: str = Field("", description="Prompt name")
    description: str = Field("", description="Prompt description")


class PatchAgentDraftApiRequest(ScopedItem):
    """Request model for new-style agent draft endpoint.

    Dual-mode for creatable resources only:
      - name/name_id, description/description_id
    ID-only for non-creatable resources:
      - flag_ids, department_ids, model_id, tool_ids, reasoning_level_ids,
        temperature_level_ids, voice_ids, rubric_ids

    Client always sends full state (append-only — each write is a new snapshot).
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name": "names",
        "name_id": "names",
        "description": "descriptions",
        "description_id": "descriptions",
        "flag_ids": "flags",
        "department_ids": "departments",
        "model_id": "models",
        "tool_ids": "tools",
        "reasoning_level_id": "reasoning_levels",
        "temperature_level_id": "temperature_levels",
        "voice_ids": "voices",
        "quality_ids": "qualities",
        "rubric_ids": "rubrics",
        "prompt_id": "prompts",
        "instruction_id": "instructions",
        "instructions_id": "instructions",
    }

    draft_id: UUID | None = Field(None, description="UUID of the draft to update")
    group_id: UUID | None = Field(None, description="UUID of the owning group")
    input_draft_id: UUID | None = Field(None, description="UUID of the input draft")
    idempotency_key: UUID | None = Field(None, description="Idempotency key for accept/reject acknowledgement")
    soft: bool = Field(False, description="Stage the draft dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Whether pending changes should be accepted")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, description="Display name value")
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    description: str | None = Field(None, description="Description text value")
    description_id: UUID | None = Field(None, description="UUID of the description resource")

    # Canonical flag ids + denormalized bool resolved server-side
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical")
    active: bool | None = Field(None, description="Denormalized agent_active flag state; resolved to a flag_ids entry server-side")
    departments: list[str] | None = Field(None, description="Department names for matching")
    department_ids: list[UUID] | None = Field(None, description="Associated department UUIDs")
    model_id: UUID | None = Field(None, description="Associated model UUID")
    tool_ids: list[UUID] | None = Field(None, description="Associated tool UUIDs")
    reasoning_level: str | None = Field(None, description="Reasoning level label to match")
    reasoning_level_id: UUID | None = Field(None, description="Associated reasoning level UUID")
    temperature_level: str | None = Field(None, description="Temperature level label to match")
    temperature_level_id: UUID | None = Field(None, description="Associated temperature level UUID")
    voices: list[str] | None = Field(None, description="Voice names for matching or creation")
    voice_ids: list[UUID] | None = Field(None, description="Associated voice UUIDs")
    qualities: list[str] | None = Field(None, description="Quality labels for matching")
    quality_ids: list[UUID] | None = Field(None, description="Associated quality UUIDs")
    prompt_id: UUID | None = Field(None, description="Associated prompt UUID")
    prompt: CreatePromptInput | None = Field(None, description="Prompt to create inline")
    instruction_id: UUID | None = Field(None, description="Associated instruction UUID")
    instructions_id: UUID | None = Field(None, description="Legacy alias for associated instruction UUID")
    rubric_ids: list[UUID] | None = Field(None, description="Associated rubric UUIDs")
    pending_ids: list[UUID] | None = Field(None, description="Pending resource identifiers")


class DraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = Field(None, description="UUID of the selected name resource")
    name: str | None = Field(None, description="Resolved name value")
    description_id: UUID | None = Field(None, description="UUID of the selected description resource")
    description: str | None = Field(None, description="Resolved description value")
    flag_ids: list[UUID] = Field(default_factory=list, description="Selected flag UUIDs")
    active: bool | None = Field(None, description="Echoed agent_active flag state")
    department_ids: list[UUID] = Field(..., description="Selected department UUIDs")
    model_id: UUID | None = Field(None, description="Selected model UUID")
    tool_ids: list[UUID] = Field(..., description="Selected tool UUIDs")
    reasoning_level_id: UUID | None = Field(None, description="Selected reasoning level UUID")
    temperature_level_id: UUID | None = Field(None, description="Selected temperature level UUID")
    voice_ids: list[UUID] = Field(..., description="Selected voice UUIDs")
    quality_ids: list[UUID] = Field(..., description="Selected quality UUIDs")
    rubric_ids: list[UUID] = Field(..., description="Selected rubric UUIDs")
    prompt_id: UUID | None = Field(None, description="Selected prompt UUID when provided")
    instruction_id: UUID | None = Field(None, description="Selected instruction UUID when provided")
    pending_ids: list[UUID] = Field(default_factory=list, description="Pending resource identifiers")


AgentDraftFormState = DraftFormState


class PatchAgentDraftApiResponse(BaseModel):
    """Response model for new-style agent draft endpoint."""

    success: bool = Field(..., description="Whether the operation succeeded")
    draft_id: UUID = Field(..., description="UUID of the saved draft")
    idempotency_key: UUID | None = Field(None, description="Idempotency key for accept/reject acknowledgement")
    message: str = Field(..., description="Human-readable result message")
    form_state: DraftFormState | None = Field(None, description="Server-authoritative form state")


class GetAgentDraftsApiRequest(BaseModel):
    """Request model for the agent drafts list endpoint.

    Mirrors ``GenerationsAgentApiRequest`` — name search +
    date window + pagination. All fields optional; an empty body
    returns the caller's most recent drafts.
    """

    search: str | None = Field(None, description="Name search (ILIKE substring)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=200, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")


class GetAgentDraftsApiResponse(BaseModel):
    """Response model for agent drafts list endpoint."""

    entries: list[GetAgentDraftResponse] | None = Field(None, description="List of agent draft entries")


# ========== List Endpoint Types ==========


# ========== Export Endpoint Types ==========


class ExportAgentApiRequest(BaseModel):
    """Request model for export agent endpoint."""

    agent_id: UUID | None = Field(None, description="UUID of the agent to export")
    idempotency_key: UUID | None = Field(None, description="Idempotency key — replays the prior export instead of re-running")
    soft: bool = Field(False, description="Stage the export dormant (active=False); ack with accept activates it")
    accept: bool | None = Field(None, description="Ack: True promotes the staged export, False rejects. Only meaningful with idempotency_key")


class ExportAgentApiResponse(BaseModel):
    """Response model for export agent endpoint."""

    file_id: UUID = Field(..., description="UUID of the files_resource holding the export CSV")
    file_name: str = Field(..., description="Suggested download file name")
    row_count: int = Field(..., description="Number of data rows in the export")
    idempotency_key: UUID | None = Field(None, description="Server-minted soft-call key (audit call_id). On a soft propose, echo this back with `accept` to promote/reject the staged export.")


class FileDownloadAgentApiRequest(BaseModel):
    """Request model for agent file download endpoint."""

    file_id: UUID = Field(..., description="UUID of the files_resource to download")


class FileDownloadAgentApiResult(BaseModel):
    """Resolved file info returned by the infra function.

    The transport layer (HTTP/WS) uses this to serve the file appropriately.
    """

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


class ListAgentApiAgent(BaseModel):
    """Agent type for list endpoint with computed permissions."""

    id: UUID | None = Field(None, description="Agent artifact UUID (canonical id; mirrors agent_id)")
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
    flag_ids: list[UUID] | None = Field(None, description="Currently selected flag option UUIDs")
    is_inactive: bool | None = Field(None, description="Whether the agent is inactive (derived from agent_active flag)")
    is_mcp: bool | None = Field(None, description="Whether the agent is exposed via MCP (derived from mcp flag)")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    can_duplicate: bool | None = Field(None, description="Whether the current user can duplicate")
    can_delete: bool | None = Field(None, description="Whether the current user can delete")
    pending_status: str | None = Field(None, description="Soft-call ledger status (pending/accepted/rejected) for the latest pending op on this row")
    pending_operation: str | None = Field(None, description="Operation name (create/update/delete/duplicate/draft) of the latest pending soft-call entry")
    pending_call_id: UUID | None = Field(None, description="Originating tool call id for the latest pending soft-call entry")


class ListAgentApiResponse(BaseModel):
    """Response model for list agent endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    agents: list[ListAgentApiAgent] | None = Field(None, description="List of agent items")
    department_filter: ListFilterSection | None = Field(None, description="Filter options for departments")
    model_filter: ListFilterSection | None = Field(None, description="Filter options for models")
    tool_filter: ListFilterSection | None = Field(None, description="Filter options for tools")
    flag_filter: ListFilterSection | None = Field(None, description="Filter options for flags in list UI")
    total_count: int | None = Field(None, description="Total number of matching records")
    import_fields: list[ImportField] | None = Field(
        None, description="CSV import column schema for the bulk-import dialog"
    )


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsAgentApiRequest(BaseModel):
    """Request model for agent generations endpoint."""

    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")


class GenerationsAgentListItem(BaseModel):
    """Single generation group in the agent generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsAgentApiResponse(BaseModel):
    """Response model for agent generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsAgentListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemAgentApiRequest(BaseModel):
    """Request model for agent problem endpoint."""

    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant problem")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ProblemAgentApiResponse(BaseModel):
    """Response model for agent problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")



# =============================================================================
# Text Download Types
# =============================================================================


class TextDownloadAgentApiRequest(BaseModel):
    """Request model for agent text download endpoint."""

    text_id: UUID = Field(..., description="UUID of the texts_resource to download")


class TextDownloadAgentApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")



# =============================================================================
# Call Download Types
# =============================================================================


class CallDownloadAgentApiRequest(BaseModel):
    """Request model for agent call download endpoint."""

    call_id: UUID = Field(..., description="UUID of the calls_resource to download")


class CallDownloadAgentApiResult(BaseModel):
    """Resolved call file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")
