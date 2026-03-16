"""Handcrafted types for persona GET endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.persona.create import CreatePersonaItem
from app.infra.v5_types import BaseResourceSection, ListFilterSection
from app.tools.entries.persona_drafts.types import GetPersonaDraftResponse
from app.tools.resources.fields.types import GetFieldResponse
from app.tools.resources.parameters.types import GetParameterResponse

# =============================================================================
# Resource Types (handcrafted — no dependency on app.sql.types)
# =============================================================================


class PersonaNameResource(BaseModel):
    """Name resource for persona."""

    id: UUID | None = None
    name: str | None = None
    generated: bool | None = None


class PersonaDescriptionResource(BaseModel):
    """Description resource for persona."""

    id: UUID | None = None
    description: str | None = None
    generated: bool | None = None


class PersonaColorResource(BaseModel):
    """Color resource for persona."""

    id: UUID | None = None
    name: str | None = None
    description: str | None = None
    hex_code: str | None = None
    generated: bool | None = None


class PersonaIconResource(BaseModel):
    """Icon resource for persona."""

    id: UUID | None = None
    name: str | None = None
    description: str | None = None
    value: str | None = None
    generated: bool | None = None


class PersonaInstructionResource(BaseModel):
    """Instruction resource for persona."""

    id: UUID | None = None
    template: str | None = None
    generated: bool | None = None


class PersonaDepartmentResource(BaseModel):
    """Department resource for persona."""

    department_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    generated: bool | None = None


class PersonaParameterFieldResource(BaseModel):
    """Parameter field resource for persona."""

    id: UUID | None = None
    field_id: UUID | None = None
    parameter_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    generated: bool | None = None


class PersonaExampleResource(BaseModel):
    """Example resource for persona."""

    id: UUID | None = None
    example: str | None = None
    generated: bool | None = None


class PersonaVoiceResource(BaseModel):
    """Voice resource for persona."""

    id: UUID | None = None
    voice: str | None = None
    generated: bool | None = None


class PersonaAgentResource(BaseModel):
    """Agent resource for persona (config chain)."""

    id: UUID | None = None
    name: str | None = None
    description: str | None = None
    model_id: UUID | None = None
    temperature: float | None = None
    reasoning: str | None = None
    tool_ids: list[UUID] | None = None
    quality: str | None = None
    voices: list[str] | None = None
    prompt_id: UUID | None = None
    instruction_ids: list[UUID] | None = None
    active: bool | None = None
    generated: bool | None = None


class PersonaModelResource(BaseModel):
    """Model resource for persona (config chain)."""

    id: UUID | None = None
    name: str | None = None
    description: str | None = None
    value: str | None = None
    provider_id: UUID | None = None
    modality_ids: list[UUID] | None = None
    temperature_level_ids: list[UUID] | None = None
    reasoning_level_ids: list[UUID] | None = None
    quality_ids: list[UUID] | None = None
    voice_ids: list[UUID] | None = None


class PersonaProviderResource(BaseModel):
    """Provider resource for persona (config chain)."""

    id: UUID | None = None
    value: str | None = None
    name: str | None = None
    description: str | None = None
    endpoint: str | None = None
    key: str | None = None
    active: bool | None = None
    generated: bool | None = None


class PersonaDraftEntry(BaseModel):
    """Persona draft entry for websocket."""

    draft_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    version: int | None = None
    generated: bool | None = None
    mcp: bool | None = None
    active: bool | None = None
    group_id: UUID | None = None
    name_ids: list[UUID] | None = None
    description_ids: list[UUID] | None = None
    color_ids: list[UUID] | None = None
    icon_ids: list[UUID] | None = None
    instruction_ids: list[UUID] | None = None
    flag_ids: list[UUID] | None = None
    department_ids: list[UUID] | None = None
    parameter_field_ids: list[UUID] | None = None
    example_ids: list[UUID] | None = None
    parameter_ids: list[UUID] | None = None
    voice_ids: list[UUID] | None = None


class GetPersonaDraftsApiResponse(BaseModel):
    """Response model for persona drafts list endpoint."""

    entries: list[GetPersonaDraftResponse] | None = Field(None, description="List of persona drafts")


class PersonaFlagConfig(BaseModel):
    """Enriched flag config for direct client consumption."""

    key: str  # e.g., "active"
    label: str  # e.g., "Active"
    description: str | None = None
    icon_id: str | None = None
    flag_option_id: UUID | None = None  # ID to use when enabling
    show: bool = True
    required: bool = False
    generated: bool | None = None


# ========== Per-Resource Section Types ==========


# Single-select sections (resource = singular current, resources = all options)
class PersonaNameSection(BaseResourceSection):
    resource: PersonaNameResource | None = None
    resources: list[PersonaNameResource] | None = None


class PersonaDescriptionSection(BaseResourceSection):
    resource: PersonaDescriptionResource | None = None
    resources: list[PersonaDescriptionResource] | None = None


class PersonaColorSection(BaseResourceSection):
    resource: PersonaColorResource | None = None
    resources: list[PersonaColorResource] | None = None


class PersonaIconSection(BaseResourceSection):
    resource: PersonaIconResource | None = None
    resources: list[PersonaIconResource] | None = None


class PersonaInstructionSection(BaseResourceSection):
    resource: PersonaInstructionResource | None = None
    resources: list[PersonaInstructionResource] | None = None


# Flag section (uses PersonaFlagConfig)
class PersonaFlagSection(BaseResourceSection):
    current: PersonaFlagConfig | None = None
    resources: list[PersonaFlagConfig] | None = None


# Multi-select sections (current = list, resources = all options)
class PersonaDepartmentSection(BaseResourceSection):
    current: list[PersonaDepartmentResource] | None = None
    resources: list[PersonaDepartmentResource] | None = None


class PersonaParameterFieldSection(BaseResourceSection):
    current: list[PersonaParameterFieldResource] | None = None
    resources: list[PersonaParameterFieldResource] | None = None


class PersonaExampleSection(BaseResourceSection):
    current: list[PersonaExampleResource] | None = None
    resources: list[PersonaExampleResource] | None = None


class PersonaParameterSection(BaseResourceSection):
    current: list[GetParameterResponse] | None = None
    resources: list[GetParameterResponse] | None = None


class PersonaVoiceSection(BaseResourceSection):
    current: list[PersonaVoiceResource] | None = None
    resources: list[PersonaVoiceResource] | None = None


class GetPersonaApiRequest(BaseModel):
    """Request model for get persona endpoint."""

    persona_id: UUID | None = Field(None, description="UUID of the persona to retrieve")
    draft_id: UUID | None = Field(None, description="UUID of the draft to load instead of published state")
    # Search filters for resources
    color_search: str | None = Field(None, description="Filter color options by search text")
    icon_search: str | None = Field(None, description="Filter icon options by search text")
    descriptions_search: str | None = Field(None, description="Filter description options by search text")
    instructions_search: str | None = Field(None, description="Filter instruction options by search text")
    parameter_field_search: str | None = Field(None, description="Filter parameter field options by search text")
    parameter_ids: list[str] | None = Field(
        None, description="Parameter group IDs to expand in the response"
    )
    # Show selected filters
    color_show_selected: bool | None = Field(None, description="When true, only return currently selected colors")
    icon_show_selected: bool | None = Field(None, description="When true, only return currently selected icons")
    parameter_field_show_selected: bool | None = Field(None, description="When true, only return currently selected parameter fields")


class GetPersonaApiResponse(BaseModel):
    """Response model for get persona endpoint."""

    # Context
    actor_name: str | None = Field(None, description="Display name of the authenticated user")
    persona_exists: bool | None = Field(None, description="Whether the requested persona exists")
    can_edit: bool | None = Field(None, description="Whether the current user has edit permission")
    disabled_reason: str | None = Field(None, description="Human-readable reason if editing is disabled")
    draft_version: int | None = Field(None, description="Current draft version number for optimistic concurrency")
    group_id: UUID | None = Field(None, description="Generation group UUID for AI operations")

    # Step-level AI generation flags
    basic_show_ai_generate: bool | None = Field(None, description="Whether AI generation is available for basic fields (name, color, icon)")
    content_show_ai_generate: bool | None = Field(None, description="Whether AI generation is available for content fields (description, instructions, examples)")
    parameters_step_show_ai_generate: bool | None = Field(None, description="Whether AI generation is available for parameter fields")

    # Per-resource sections
    names: PersonaNameSection | None = Field(None, description="Name resource section with current selection and options")
    descriptions: PersonaDescriptionSection | None = Field(None, description="Description resource section with current selection and options")
    colors: PersonaColorSection | None = Field(None, description="Color resource section with current selection and options")
    icons: PersonaIconSection | None = Field(None, description="Icon resource section with current selection and options")
    instructions: PersonaInstructionSection | None = Field(None, description="Instruction resource section with current selection and options")
    flags: PersonaFlagSection | None = Field(None, description="Boolean flag configuration section (e.g. active status)")
    departments: PersonaDepartmentSection | None = Field(None, description="Department association section with current selections and options")
    parameter_fields: PersonaParameterFieldSection | None = Field(None, description="Parameter field section with current selections and options")
    examples: PersonaExampleSection | None = Field(None, description="Example resource section with current selections and options")
    parameters: PersonaParameterSection | None = Field(None, description="Parameter section with current selections and options")
    voices: PersonaVoiceSection | None = Field(None, description="Voice resource section with current selections and options")
    # Fields catalog (not a section — computed resource, never saved)
    fields: list[GetFieldResponse] | None = Field(None, description="All available field definitions (computed, never saved)")
    # Resolved parameter IDs (derived from saved parameter_fields)
    resolved_parameter_ids: list[str] | None = Field(None, description="Parameter IDs derived from saved parameter_fields")


class PersonaResourceBucket(BaseModel):
    """Generic resources bucket with full objects (always plural lists)."""

    names: list[PersonaNameResource] | None = None
    descriptions: list[PersonaDescriptionResource] | None = None
    colors: list[PersonaColorResource] | None = None
    icons: list[PersonaIconResource] | None = None
    instructions: list[PersonaInstructionResource] | None = None
    flags: list[PersonaFlagConfig] | None = None
    departments: list[PersonaDepartmentResource] | None = None
    parameter_fields: list[PersonaParameterFieldResource] | None = None
    examples: list[PersonaExampleResource] | None = None
    parameters: list[GetParameterResponse] | None = None
    voices: list[PersonaVoiceResource] | None = None
    fields: list[GetFieldResponse] | None = None


class PersonaResources(BaseModel):
    """Full resources + current selections."""

    resources: PersonaResourceBucket | None = None
    current: PersonaResourceBucket | None = None


# ========== Internal Data Types ==========


@dataclass
class PersonaInternalData:
    """Internal data from core persona fetching (cacheable layer).

    This dataclass contains all computed data needed by both:
    - get_persona_websocket() - minimal data for WebSocket handlers
    - get_persona_impl() - canonical full artifact bundle for all surfaces
    """

    # Access/context
    actor_name: str | None
    persona_exists: bool | None
    can_edit: bool
    disabled_reason: str | None
    draft_version: int | None
    group_id: UUID | None

    # Agent mappings (resource_type -> agent_id)
    agent_ids: dict[str, UUID | None]

    # Show/required flags
    show_flags_map: dict[str, bool]
    required_flags_map: dict[str, bool]

    # Suggestions (resource -> list of suggestion IDs)
    suggestions_map: dict[str, list[UUID]]

    # Show AI generate flags (computed: agent exists for resource)
    show_ai_generate_map: dict[str, bool]
    basic_show_ai_generate: bool
    content_show_ai_generate: bool
    parameters_step_show_ai_generate: bool

    # Resources payload
    resources_payload: PersonaResources

    # Per-resource tool IDs (from selected agents)
    tool_ids_map: dict[str, UUID | None]

    # Resolved parameter IDs (derived from saved parameter_fields)
    resolved_parameter_ids: list[str]

    # Config resources (from denormalized chain, for generation)
    config_agent_resources: list[PersonaAgentResource] | None
    config_model_resources: list[PersonaModelResource] | None
    config_provider_resources: list[PersonaProviderResource] | None


# ========== Import Field Types ==========


class ImportField(BaseModel):
    """Field descriptor for CSV import column mapping."""

    key: str
    label: str
    required: bool = False
    multi: bool = False
    type: str = "string"
    example: str | None = None
    description: str | None = None


# ========== List Endpoint Types ==========


class ListPersonaApiPersona(BaseModel):
    """Persona type for list endpoint with computed permissions."""

    persona_id: UUID | None = Field(None, description="UUID of the persona")
    name: str | None = Field(None, description="Display name")
    description: str | None = Field(None, description="Persona description text")
    color: str | None = Field(None, description="Hex color code")
    icon: str | None = Field(None, description="Icon identifier")
    department_ids: list[str] | None = Field(None, description="Associated department UUIDs")
    scenario_ids: list[UUID] | None = Field(None, description="Scenarios using this persona")
    field_ids: list[UUID] | None = Field(None, description="Associated field UUIDs")
    is_inactive: bool | None = Field(None, description="Whether the persona is marked inactive")
    generated: bool | None = Field(None, description="Whether the persona was AI-generated")
    mcp: bool | None = Field(None, description="Whether this persona uses MCP tooling")
    num_scenarios: int | None = Field(None, description="Count of scenarios using this persona")
    num_profiles: int | None = Field(None, description="Count of profiles who have interacted with this persona")
    # Computed in Python
    can_edit: bool | None = Field(None, description="Whether the current user can edit this persona")
    can_duplicate: bool | None = Field(None, description="Whether the current user can duplicate this persona")
    can_delete: bool | None = Field(None, description="Whether the current user can delete this persona")
    updated_at: datetime | None = Field(None, description="Last modification timestamp")


class ListPersonaApiResponse(BaseModel):
    """Response model for list persona endpoint with computed permissions."""

    actor_name: str | None = Field(None, description="Display name of the authenticated user")
    personas: list[ListPersonaApiPersona] | None = Field(None, description="List of personas with computed permissions")
    # Core filters
    scenario_filter: ListFilterSection | None = Field(None, description="Scenario filter options for the list UI")
    field_filter: ListFilterSection | None = Field(None, description="Field filter options for the list UI")
    department_filter: ListFilterSection | None = Field(None, description="Department filter options for the list UI")
    # Bulk edit filters
    color_filter: ListFilterSection | None = Field(None, description="Color filter options for bulk edit")
    icon_filter: ListFilterSection | None = Field(None, description="Icon filter options for bulk edit")
    voice_filter: ListFilterSection | None = Field(None, description="Voice filter options for bulk edit")
    instruction_filter: ListFilterSection | None = Field(None, description="Instruction filter options for bulk edit")
    total_count: int | None = Field(None, description="Total number of personas matching filters")


# ========== Shared Save/Create/Update Types ==========


class PersonaFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field that failed validation")
    message: str = Field(..., description="Human-readable validation error message")


class PersonaResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded for this item")
    persona_id: UUID | None = Field(None, description="UUID of the affected persona")
    message: str = Field(..., description="Human-readable result message")
    errors: list[PersonaFieldError] | None = Field(None, description="Per-field validation errors, if any")


# ========== Create Endpoint Types ==========


class CreatePersonaApiRequest(BaseModel):
    """Request model for bulk create persona endpoint."""

    personas: list[CreatePersonaItem] = Field(..., description="List of persona items to create")


class CreatePersonaApiResponse(BaseModel):
    """Response model for bulk create persona endpoint."""

    results: list[PersonaResultItem] = Field(..., description="Per-persona creation results")


# ========== Update Endpoint Types ==========


class UpdatePersonaItem(BaseModel):
    """Single persona item for update — persona_id required, all fields optional.

    Only provided fields are updated (partial update).
    """

    persona_id: UUID = Field(..., description="UUID of the persona to update (required)")
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of an existing name resource to select")
    name: str | None = Field(None, description="Display name text (creates new resource if name_id not provided)")
    color_id: UUID | None = Field(None, description="UUID of an existing color resource to select")
    color: str | None = Field(None, description="Hex color code (creates new resource if color_id not provided)")
    icon_id: UUID | None = Field(None, description="UUID of an existing icon resource to select")
    icon: str | None = Field(None, description="Icon identifier value (creates new resource if icon_id not provided)")
    instructions_id: UUID | None = Field(None, description="UUID of an existing instruction resource to select")
    instructions: str | None = Field(None, description="System instruction template (creates new resource if instructions_id not provided)")
    description_id: UUID | None = Field(None, description="UUID of an existing description resource to select")
    description: str | None = Field(None, description="Persona description text (creates new resource if description_id not provided)")
    active_flag_id: UUID | None = Field(None, description="UUID of the flag option to set active status")
    active_flag: bool | None = Field(None, description="Whether the persona is active (resolved to flag_id)")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to associate (replaces existing)")
    departments: list[str] | None = Field(None, description="Department names (resolved to UUIDs server-side)")
    parameter_field_ids: list[UUID] | None = Field(None, description="Parameter field UUIDs to associate (replaces existing)")
    parameter_fields: list[str] | None = Field(None, description="Parameter field names (resolved to UUIDs server-side)")
    example_ids: list[UUID] | None = Field(None, description="Example resource UUIDs to associate (replaces existing)")
    examples: list[str] | None = Field(None, description="Example texts (creates new example resources)")
    voice_ids: list[UUID] | None = Field(None, description="Voice resource UUIDs to associate (replaces existing)")
    voices: list[str] | None = Field(None, description="Voice values (resolved to UUIDs server-side)")


class UpdatePersonaApiRequest(BaseModel):
    """Request model for bulk update persona endpoint."""

    personas: list[UpdatePersonaItem] = Field(..., description="List of persona items to update")


class UpdatePersonaApiResponse(BaseModel):
    """Response model for bulk update persona endpoint."""

    results: list[PersonaResultItem] = Field(..., description="Per-persona update results")


class SavePersonaFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str
    message: str


# ========== Delete Endpoint Types ==========


class DeletePersonaApiRequest(BaseModel):
    """Request model for bulk delete persona endpoint."""

    persona_ids: list[UUID] = Field(..., description="List of persona UUIDs to delete")


class DeletePersonaResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    persona_id: UUID = Field(..., description="UUID of the deleted persona")
    message: str = Field(..., description="Human-readable result message")


class DeletePersonaApiResponse(BaseModel):
    """Response model for bulk delete persona endpoint."""

    results: list[DeletePersonaResult] = Field(..., description="Per-persona deletion results")


# ========== Duplicate Endpoint Types ==========


class DuplicatePersonaApiRequest(BaseModel):
    """Request model for duplicate persona endpoint."""

    persona_id: UUID = Field(..., description="UUID of the persona to duplicate")


class DuplicatePersonaApiResponse(BaseModel):
    """Response model for duplicate persona endpoint."""

    success: bool = Field(..., description="Whether the duplication succeeded")
    persona_id: UUID = Field(..., description="UUID of the newly created duplicate persona")
    message: str = Field(..., description="Human-readable result message")


# ========== Draft Endpoint Types (composable infra) ==========


class PatchPersonaDraftApiRequest(BaseModel):
    """Request model for new-style persona draft endpoint.

    Dual-mode for creatable resources only:
      - name/name_id, description/description_id, instructions/instructions_id, examples/example_ids
    ID-only for non-creatable resources:
      - color_id, icon_id, flag_id, department_ids, parameter_field_ids, voice_ids

    Client always sends full state (append-only — each write is a new version snapshot).
    """

    input_draft_id: UUID | None = Field(None, description="Existing draft UUID to patch (omit to create a new draft)")
    expected_version: int = Field(0, description="Expected draft version for optimistic concurrency control")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, description="Display name text (creates new name resource)")
    name_id: UUID | None = Field(None, description="UUID of an existing name resource to select")
    description: str | None = Field(None, description="Description text (creates new description resource)")
    description_id: UUID | None = Field(None, description="UUID of an existing description resource to select")
    instructions: str | None = Field(None, description="Instruction template text (creates new instruction resource)")
    instructions_id: UUID | None = Field(None, description="UUID of an existing instruction resource to select")

    # Creatable multi-select — provide values or IDs
    examples: list[str] | None = Field(None, description="Example texts (creates new example resources)")
    example_ids: list[UUID] | None = Field(None, description="Existing example resource UUIDs to select")

    # Non-creatable — ID-only
    color_id: UUID | None = Field(None, description="UUID of a color resource to select")
    icon_id: UUID | None = Field(None, description="UUID of an icon resource to select")
    flag_id: UUID | None = Field(None, description="UUID of a flag option to set")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to associate")
    parameter_field_ids: list[UUID] | None = Field(None, description="Parameter field UUIDs to associate")
    voice_ids: list[UUID] | None = Field(None, description="Voice resource UUIDs to associate")


class DraftFormState(BaseModel):
    """Full form state after draft patch — server is source of truth.

    Client replaces its local form state with this after every successful patch.
    """

    name_id: UUID | None = Field(None, description="Currently selected name resource UUID")
    description_id: UUID | None = Field(None, description="Currently selected description resource UUID")
    instructions_id: UUID | None = Field(None, description="Currently selected instruction resource UUID")
    color_id: UUID | None = Field(None, description="Currently selected color resource UUID")
    icon_id: UUID | None = Field(None, description="Currently selected icon resource UUID")
    active_flag_id: UUID | None = Field(None, description="Currently selected flag option UUID")
    department_ids: list[UUID] = Field(default_factory=list, description="Currently associated department UUIDs")
    example_ids: list[UUID] = Field(default_factory=list, description="Currently associated example resource UUIDs")
    parameter_field_ids: list[UUID] = Field(default_factory=list, description="Currently associated parameter field UUIDs")
    voice_ids: list[UUID] = Field(default_factory=list, description="Currently associated voice resource UUIDs")


class PatchPersonaDraftApiResponse(BaseModel):
    """Response model for new-style persona draft endpoint."""

    success: bool = Field(..., description="Whether the draft operation succeeded")
    draft_id: UUID = Field(..., description="UUID of the created or updated draft")
    new_version: int = Field(..., description="New draft version number after this patch")
    message: str = Field(..., description="Human-readable result message")
    form_state: DraftFormState = Field(..., description="Complete form state after patch — client should replace local state")


# ========== Export Endpoint Types ==========


class ExportPersonaApiRequest(BaseModel):
    """Request model for export persona endpoint."""

    persona_id: UUID | None = Field(None, description="UUID of a specific persona to export (omit for bulk export)")

    # Same filters as list endpoint
    search: str | None = Field(None, description="Filter personas by search text")
    scenario_ids: list[str] | None = Field(None, description="Filter to personas used in these scenarios")
    field_ids: list[str] | None = Field(None, description="Filter to personas with these fields")
    filter_department_ids: list[str] | None = Field(None, description="Filter to personas in these departments")


class ExportPersonaApiResponse(BaseModel):
    """Response model for export persona endpoint."""

    content: str = Field(..., description="CSV content as a string")
    file_name: str = Field(..., description="Suggested download file name")
    mime_type: str = Field(..., description="MIME type of the export (text/csv)")
    row_count: int = Field(..., description="Number of data rows in the export")
