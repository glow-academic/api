"""Handcrafted types for persona GET endpoint."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar  # used by RESOURCE_TYPE_MAP
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.api_types import ListFilterSection
from app.infra.resource_type_filter import ScopedItem
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
    suggested: bool = False
    selected: bool = False
    pending: bool = False


class PersonaDescriptionResource(BaseModel):
    """Description resource for persona."""

    id: UUID | None = None
    description: str | None = None
    generated: bool | None = None
    suggested: bool = False
    selected: bool = False
    pending: bool = False


class PersonaColorResource(BaseModel):
    """Color resource for persona."""

    id: UUID | None = None
    name: str | None = None
    description: str | None = None
    hex_code: str | None = None
    generated: bool | None = None
    suggested: bool = False
    selected: bool = False
    pending: bool = False


class PersonaIconResource(BaseModel):
    """Icon resource for persona."""

    id: UUID | None = None
    name: str | None = None
    description: str | None = None
    value: str | None = None
    generated: bool | None = None
    suggested: bool = False
    selected: bool = False
    pending: bool = False


class PersonaInstructionResource(BaseModel):
    """Instruction resource for persona."""

    id: UUID | None = None
    template: str | None = None
    generated: bool | None = None
    suggested: bool = False
    selected: bool = False
    pending: bool = False


class PersonaDepartmentResource(BaseModel):
    """Department resource for persona."""

    department_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    generated: bool | None = None
    suggested: bool = False
    selected: bool = False
    pending: bool = False


class PersonaParameterFieldResource(BaseModel):
    """Parameter field resource for persona."""

    id: UUID | None = None
    field_id: UUID | None = None
    parameter_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    conditional_parameter_id: str | None = None
    generated: bool | None = None
    suggested: bool = False
    selected: bool = False
    pending: bool = False


class PersonaExampleResource(BaseModel):
    """Example resource for persona."""

    id: UUID | None = None
    example: str | None = None
    generated: bool | None = None
    suggested: bool = False
    selected: bool = False
    pending: bool = False


class PersonaVoiceResource(BaseModel):
    """Voice resource for persona."""

    id: UUID | None = None
    voice: str | None = None
    generated: bool | None = None
    suggested: bool = False
    selected: bool = False
    pending: bool = False


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


class PersonaFlagResource(BaseModel):
    """Flag option row — one per (name, type, value) entry in flags_resource."""

    id: UUID | None = Field(None, description="Flag resource identifier")
    name: str | None = Field(None, description="Flag display name")
    type: str | None = Field(None, description="Flag type (e.g. 'persona_active')")
    value: bool | None = Field(None, description="Underlying bool value of this option")
    description: str | None = Field(None, description="Flag description text")
    icon_id: UUID | None = Field(None, description="Icon identifier for the flag")
    icon: str | None = Field(None, description="Resolved SVG markup (hydrated from icons_resource)")
    generated: bool | None = Field(None, description="Whether the flag was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class SectionFilter(BaseModel):
    """Per-section filter options for GET requests."""

    search: str | None = Field(None, description="Filter options by search text")
    limit: int | None = Field(None, description="Max options to return")
    selected: bool | None = Field(None, description="Only return selected items")
    suggested: bool | None = Field(None, description="Only return suggested items")
    include: bool | None = Field(None, description="Include this section in response (default true)")
    parameter_ids: list[str] | None = Field(None, description="Parameter group IDs to filter by (parameter_fields section only)")


class GetPersonaApiRequest(BaseModel):
    """Request model for get persona endpoint."""

    id: UUID | None = Field(None, description="UUID of the persona to retrieve")
    draft_id: UUID | None = Field(None, description="UUID of the draft to load instead of published state")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")
    # Per-section filters
    names: SectionFilter | None = Field(None, description="Filter options for names section")
    descriptions: SectionFilter | None = Field(None, description="Filter options for descriptions section")
    colors: SectionFilter | None = Field(None, description="Filter options for colors section")
    icons: SectionFilter | None = Field(None, description="Filter options for icons section")
    instructions: SectionFilter | None = Field(None, description="Filter options for instructions section")
    departments: SectionFilter | None = Field(None, description="Filter options for departments section")
    examples: SectionFilter | None = Field(None, description="Filter options for examples section")
    parameter_fields: SectionFilter | None = Field(None, description="Filter options for parameter fields section")
    voices: SectionFilter | None = Field(None, description="Filter options for voices section")


class GetPersonaApiResponse(BaseModel):
    """Response model for get persona endpoint."""

    # Context
    actor_name: str | None = Field(None, description="Display name of the authenticated user")
    persona_exists: bool | None = Field(None, description="Whether the requested persona exists")
    can_edit: bool | None = Field(None, description="Whether the current user has edit permission")
    disabled_reason: str | None = Field(None, description="Human-readable reason if editing is disabled")
    group_id: UUID | None = Field(None, description="Generation group UUID for AI operations")

    # AI generation flag (user has draft permission)
    show_ai_generate: bool | None = Field(None, description="Whether AI generation is available")

    # Per-resource lists (flat arrays with selected/suggested flags)
    names: list[PersonaNameResource] | None = Field(None, description="Name resources with selected/suggested flags")
    descriptions: list[PersonaDescriptionResource] | None = Field(None, description="Description resources with selected/suggested flags")
    colors: list[PersonaColorResource] | None = Field(None, description="Color resources with selected/suggested flags")
    icons: list[PersonaIconResource] | None = Field(None, description="Icon resources with selected/suggested flags")
    instructions: list[PersonaInstructionResource] | None = Field(None, description="Instruction resources with selected/suggested flags")
    flags: list[PersonaFlagResource] | None = Field(None, description="Flag resources (one per flags_resource row, value=true/false)")
    departments: list[PersonaDepartmentResource] | None = Field(None, description="Department resources with selected/suggested flags")
    parameter_fields: list[PersonaParameterFieldResource] | None = Field(None, description="Parameter field resources with selected/suggested flags")
    examples: list[PersonaExampleResource] | None = Field(None, description="Example resources with selected/suggested flags")
    parameters: list | None = Field(None, description="Parameter resources")
    voices: list[PersonaVoiceResource] | None = Field(None, description="Voice resources with selected/suggested flags")
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
    flags: list[PersonaFlagResource] | None = None
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
    group_id: UUID | None

    # Agent mappings (resource_type -> agent_id)
    agent_ids: dict[str, UUID | None]

    # Show/required flags
    show_flags_map: dict[str, bool]
    required_flags_map: dict[str, bool]

    # Suggestions (resource -> list of suggestion IDs)
    suggestions_map: dict[str, list[UUID]]

    # AI generation flag
    show_ai_generate: bool

    # Resources payload
    resources_payload: PersonaResources

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
    flag_filter: ListFilterSection | None = Field(None, description="Flag filter options for bulk edit")
    total_count: int | None = Field(None, description="Total number of personas matching filters")


# ========== Shared Save/Create/Update Types ==========


class PersonaFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field that failed validation")
    message: str = Field(..., description="Human-readable validation error message")


class PersonaResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded for this item")
    id: UUID | None = Field(None, description="UUID of the affected persona")
    message: str = Field(..., description="Human-readable result message")
    errors: list[PersonaFieldError] | None = Field(None, description="Per-field validation errors, if any")


# ========== Create Endpoint Types ==========


class CreatePersonaItem(ScopedItem):
    """Single persona item for create — no persona_id.

    Required fields (name, color, icon, instructions): provide ID or value.
    """

    id: UUID | None = Field(None, description="Client-provided UUID for the new persona")
    resource_id: UUID | None = Field(None, description="Optional preset UUID for the resource snapshot")

    # Required single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of an existing name resource")
    name: str | None = Field(None, description="Display name text (creates new resource if name_id not provided)")
    color_id: UUID | None = Field(None, description="UUID of an existing color resource")
    color: str | None = Field(None, description="Hex color code, e.g. '#FF5733' (creates new resource if color_id not provided)")
    icon_id: UUID | None = Field(None, description="UUID of an existing icon resource")
    icon: str | None = Field(None, description="Resolved SVG markup for the icon (hydrated from icons_resource)")
    icon: str | None = Field(None, description="Icon identifier value (creates new resource if icon_id not provided)")
    instructions_id: UUID | None = Field(None, description="UUID of an existing instruction resource")
    instructions: str | None = Field(None, description="System instruction template (creates new resource if instructions_id not provided)")
    # Optional single-select — provide ID or value
    description_id: UUID | None = Field(None, description="UUID of an existing description resource")
    description: str | None = Field(None, description="Persona description text (creates new resource if description_id not provided)")
    # Canonical flag state — ids of selected flag-resource rows. Denormalized
    # booleans (`active`) are resolved to a flag_ids entry server-side.
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    active: bool | None = Field(None, description="Denormalized persona_active flag state; resolved to a flag_ids entry server-side")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to associate with this persona")
    departments: list[str] | None = Field(None, description="Department names (resolved to UUIDs server-side)")
    parameter_field_ids: list[UUID] | None = Field(None, description="Parameter field UUIDs to associate")
    parameter_fields: list[str] | None = Field(None, description="Parameter field names (resolved to UUIDs server-side)")
    example_ids: list[UUID] | None = Field(None, description="Existing example resource UUIDs to associate")
    examples: list[str] | None = Field(None, description="Example texts (creates new example resources)")
    voice_ids: list[UUID] | None = Field(None, description="Voice resource UUIDs to associate")
    voices: list[str] | None = Field(None, description="Voice values (resolved to UUIDs server-side)")

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name": "names",
        "name_id": "names",
        "description": "descriptions",
        "description_id": "descriptions",
        "color": "colors",
        "color_id": "colors",
        "icon": "icons",
        "icon_id": "icons",
        "instructions": "instructions",
        "instructions_id": "instructions",
        "flag_ids": "flags",
        "active": "flags",
        "departments": "departments",
        "department_ids": "departments",
        "parameter_fields": "parameter_fields",
        "parameter_field_ids": "parameter_fields",
        "examples": "examples",
        "example_ids": "examples",
        "voices": "voices",
        "voice_ids": "voices",
    }


class CreatePersonaApiRequest(BaseModel):
    """Request model for bulk create persona endpoint.

    Two body shapes:
      - First call: ``personas`` required.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant artifact by ``idempotency_key``.
    """

    personas: list[CreatePersonaItem] | None = Field(
        None, description="List of persona items to create (required on first call)",
    )

    # Ack
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant create")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class CreatePersonaApiResponse(BaseModel):
    """Response model for bulk create persona endpoint."""

    results: list[PersonaResultItem] = Field(..., description="Per-persona creation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
    personas: list[ListPersonaApiPersona] | None = Field(
        None, description="Hydrated rows for the successfully-created personas (mirrors /persona/search shape)",
    )


# ========== Update Endpoint Types ==========


class UpdatePersonaItem(ScopedItem):
    """Single persona item for update — id required, all fields optional.

    Only provided fields are updated (partial update).
    """

    id: UUID = Field(..., description="UUID of the persona to update (required)")
    # Optional single-select — provide ID or value
    name_id: UUID | None = Field(None, description="UUID of an existing name resource to select")
    name: str | None = Field(None, description="Display name text (creates new resource if name_id not provided)")
    color_id: UUID | None = Field(None, description="UUID of an existing color resource to select")
    color: str | None = Field(None, description="Hex color code (creates new resource if color_id not provided)")
    icon_id: UUID | None = Field(None, description="UUID of an existing icon resource to select")
    icon: str | None = Field(None, description="Resolved SVG markup for the icon (hydrated from icons_resource)")
    icon: str | None = Field(None, description="Icon identifier value (creates new resource if icon_id not provided)")
    instructions_id: UUID | None = Field(None, description="UUID of an existing instruction resource to select")
    instructions: str | None = Field(None, description="System instruction template (creates new resource if instructions_id not provided)")
    description_id: UUID | None = Field(None, description="UUID of an existing description resource to select")
    description: str | None = Field(None, description="Persona description text (creates new resource if description_id not provided)")
    # Canonical flag state — ids of selected flag-resource rows. Denormalized
    # booleans (`active`) are resolved to a flag_ids entry server-side.
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    active: bool | None = Field(None, description="Denormalized persona_active flag state; resolved to a flag_ids entry server-side")
    # Optional multi-select — provide IDs or values
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to associate (replaces existing)")
    departments: list[str] | None = Field(None, description="Department names (resolved to UUIDs server-side)")
    parameter_field_ids: list[UUID] | None = Field(None, description="Parameter field UUIDs to associate (replaces existing)")
    parameter_fields: list[str] | None = Field(None, description="Parameter field names (resolved to UUIDs server-side)")
    example_ids: list[UUID] | None = Field(None, description="Example resource UUIDs to associate (replaces existing)")
    examples: list[str] | None = Field(None, description="Example texts (creates new example resources)")
    voice_ids: list[UUID] | None = Field(None, description="Voice resource UUIDs to associate (replaces existing)")
    voices: list[str] | None = Field(None, description="Voice values (resolved to UUIDs server-side)")

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = CreatePersonaItem.RESOURCE_TYPE_MAP


class UpdatePersonaPatch(UpdatePersonaItem):
    """Shared patch for bulk-update-all-matching mode.

    Inherits every field from ``UpdatePersonaItem`` and just relaxes
    ``id`` to optional — the bulk impl stamps the resolved id onto a
    clone of the patch per matched row, so any client-supplied id is
    ignored. Sparse semantics: only fields the client sets are written.
    """

    id: UUID | None = Field(  # type: ignore[assignment]
        None,
        description="Ignored — bulk impl stamps the resolved persona id per matched row",
    )


class UpdatePersonaApiRequest(BaseModel):
    """Request model for bulk update persona endpoint.

    Three body shapes:
      - First call (explicit): ``personas`` required — per-row patches.
      - First call (all-matching): ``all=true`` plus the filter fields
        ``/persona/search`` accepts plus a single shared ``patch`` that
        every matched row receives. The impl resolves matching ids,
        subtracts ``excluded_ids``, and runs the existing per-row
        update flow with the patch cloned per id.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant update by ``idempotency_key``.
    """

    personas: list[UpdatePersonaItem] | None = Field(
        None, description="List of persona items to update (required on first call when ``all`` is false)",
    )

    # All-matching path. Same shape as DeletePersonaApiRequest; ``patch``
    # is the shared change set applied to every matched row. ``patch.id``
    # is ignored — each resolved id is stamped onto a clone before the
    # per-row update fires.
    all: bool | None = Field(False, description="When true, apply ``patch`` to every persona matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    patch: UpdatePersonaPatch | None = Field(None, description="Shared change set applied to every matched row when ``all=true`` (sparse — only set fields are updated; ``patch.id`` ignored)")
    search: str | None = Field(None, description="Full-text search query")
    scenario_ids: list[UUID] | None = Field(None, description="Filter by scenario UUIDs")
    field_ids: list[UUID] | None = Field(None, description="Filter by field UUIDs")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    scenario_search: str | None = Field(None, description="Search text for scenario facet (no-op for row filtering)")
    field_search: str | None = Field(None, description="Search text for field facet (no-op for row filtering)")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    color_search: str | None = Field(None, description="Search text for color facet (no-op for row filtering)")
    icon_search: str | None = Field(None, description="Search text for icon facet (no-op for row filtering)")
    voice_search: str | None = Field(None, description="Search text for voice facet (no-op for row filtering)")
    instruction_search: str | None = Field(None, description="Search text for instruction facet (no-op for row filtering)")

    # Ack
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant update")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class UpdatePersonaApiResponse(BaseModel):
    """Response model for bulk update persona endpoint."""

    results: list[PersonaResultItem] = Field(..., description="Per-persona update results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
    personas: list[ListPersonaApiPersona] | None = Field(
        None, description="Hydrated rows for the successfully-updated personas (mirrors /persona/search shape)",
    )


class SavePersonaFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str
    message: str


# ========== Delete Endpoint Types ==========


class DeletePersonaApiRequest(BaseModel):
    """Request model for bulk delete persona endpoint.

    Three body shapes:
      - First call (explicit): ``ids`` required.
      - First call (all-matching): ``all=true`` plus the same filter
        fields ``/persona/search`` accepts. The impl resolves every
        matching id server-side, subtracts ``excluded_ids``, and runs
        the existing per-row delete flow.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant deletion by ``idempotency_key``.
    """

    ids: list[UUID] | None = Field(
        None, description="List of persona UUIDs to delete (required on first call when ``all`` is false)",
    )

    # All-matching path. Field names mirror ``SearchPersonaApiRequest``
    # so the client can pass URL-backed nuqs filter state through to a
    # bulk delete unchanged. Independent class (not a shared "filter"
    # sub-model) so future divergence from search predicates is trivial
    # — e.g. delete might exclude rows referenced by active scenarios.
    all: bool | None = Field(False, description="When true, delete every persona matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    # Filter fields (same shape as /persona/search). Only meaningful
    # when ``all=true``; the validator does not enforce that today —
    # the impl simply ignores them when ``ids`` is set.
    search: str | None = Field(None, description="Full-text search query")
    scenario_ids: list[UUID] | None = Field(None, description="Filter by scenario UUIDs")
    field_ids: list[UUID] | None = Field(None, description="Filter by field UUIDs")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    scenario_search: str | None = Field(None, description="Search text for scenario facet (no-op for row filtering)")
    field_search: str | None = Field(None, description="Search text for field facet (no-op for row filtering)")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    color_search: str | None = Field(None, description="Search text for color facet (no-op for row filtering)")
    icon_search: str | None = Field(None, description="Search text for icon facet (no-op for row filtering)")
    voice_search: str | None = Field(None, description="Search text for voice facet (no-op for row filtering)")
    instruction_search: str | None = Field(None, description="Search text for instruction facet (no-op for row filtering)")

    # Ack
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — confirms or rejects a dormant delete")
    accept: bool | None = Field(None, description="Accept (confirm deletion) or reject (restore). Only meaningful with idempotency_key")


class DeletePersonaResult(BaseModel):
    """Per-item result within a bulk delete response."""

    success: bool = Field(..., description="Whether the deletion succeeded")
    id: UUID = Field(..., description="UUID of the deleted persona")
    message: str = Field(..., description="Human-readable result message")


class DeletePersonaApiResponse(BaseModel):
    """Response model for bulk delete persona endpoint."""

    results: list[DeletePersonaResult] = Field(..., description="Per-persona deletion results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# ========== Duplicate Endpoint Types ==========


class DuplicatePersonaApiRequest(BaseModel):
    """Request model for duplicate persona endpoint.

    Two body shapes:
      - First call: ``id`` required.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant copy by ``idempotency_key``.
    """

    id: UUID | None = Field(
        None, description="UUID of the persona to duplicate (required on first call)",
    )

    # Ack
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant duplicate")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DuplicatePersonaApiResponse(BaseModel):
    """Response model for duplicate persona endpoint."""

    success: bool = Field(..., description="Whether the duplication succeeded")
    id: UUID = Field(..., description="UUID of the newly created duplicate persona")
    message: str = Field(..., description="Human-readable result message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
    personas: list[ListPersonaApiPersona] | None = Field(
        None, description="Hydrated row for the newly-created duplicate persona (single-element list)",
    )


# ========== Draft Endpoint Types (composable infra) ==========


class PatchPersonaDraftApiRequest(ScopedItem):
    """Request model for persona draft endpoint.

    All resources accept value or ID, matching create/update.
    Client always sends full state (append-only — each write is a new snapshot).
    """

    draft_id: UUID | None = Field(None, description="Existing draft UUID to patch (omit to create a new draft)")

    # Single-select — provide value or ID
    name: str | None = Field(None, description="Display name text (creates new name resource)")
    name_id: UUID | None = Field(None, description="UUID of an existing name resource to select")
    description: str | None = Field(None, description="Description text (creates new description resource)")
    description_id: UUID | None = Field(None, description="UUID of an existing description resource to select")
    color: str | None = Field(None, description="Hex color code (creates new resource if color_id not provided)")
    color_id: UUID | None = Field(None, description="UUID of a color resource to select")
    icon: str | None = Field(None, description="Icon identifier value (creates new resource if icon_id not provided)")
    icon_id: UUID | None = Field(None, description="UUID of an icon resource to select")
    icon: str | None = Field(None, description="Resolved SVG markup for the icon (hydrated from icons_resource)")
    instructions: str | None = Field(None, description="Instruction template text (creates new instruction resource)")
    instructions_id: UUID | None = Field(None, description="UUID of an existing instruction resource to select")
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    active: bool | None = Field(None, description="Denormalized persona_active flag state; resolved to a flag_ids entry server-side")

    # Multi-select — provide values or IDs
    examples: list[str] | None = Field(None, description="Example texts (creates new example resources)")
    example_ids: list[UUID] | None = Field(None, description="Existing example resource UUIDs to select")
    department_ids: list[UUID] | None = Field(None, description="Department UUIDs to associate")
    departments: list[str] | None = Field(None, description="Department names (resolved to UUIDs server-side)")
    parameter_field_ids: list[UUID] | None = Field(None, description="Parameter field UUIDs to associate")
    parameter_fields: list[str] | None = Field(None, description="Parameter field names (resolved to UUIDs server-side)")
    voice_ids: list[UUID] | None = Field(None, description="Voice resource UUIDs to associate")
    voices: list[str] | None = Field(None, description="Voice values (resolved to UUIDs server-side)")

    # Pending state
    pending_ids: list[UUID] | None = Field(None, description="Resource IDs to keep as pending (active=false on connection)")

    # Ack
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant draft")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name": "names",
        "name_id": "names",
        "description": "descriptions",
        "description_id": "descriptions",
        "color": "colors",
        "color_id": "colors",
        "icon": "icons",
        "icon_id": "icons",
        "instructions": "instructions",
        "instructions_id": "instructions",
        "flag_ids": "flags",
        "examples": "examples",
        "example_ids": "examples",
        "departments": "departments",
        "department_ids": "departments",
        "parameter_fields": "parameter_fields",
        "parameter_field_ids": "parameter_fields",
        "voices": "voices",
        "voice_ids": "voices",
    }


class DraftFormState(BaseModel):
    """Full form state after draft patch — server is source of truth.

    Client replaces its local form state with this after every successful patch.
    Includes both resolved IDs and echoed values for AI model feedback.
    """

    name_id: UUID | None = Field(None, description="Currently selected name resource UUID")
    name: str | None = Field(None, description="Name value that was saved")
    description_id: UUID | None = Field(None, description="Currently selected description resource UUID")
    description: str | None = Field(None, description="Description value that was saved")
    instructions_id: UUID | None = Field(None, description="Currently selected instruction resource UUID")
    instructions: str | None = Field(None, description="Instructions value that was saved")
    color_id: UUID | None = Field(None, description="Currently selected color resource UUID")
    color: str | None = Field(None, description="Color value that was saved (hex code)")
    icon_id: UUID | None = Field(None, description="Currently selected icon resource UUID")
    icon: str | None = Field(None, description="Resolved SVG markup for the icon (hydrated from icons_resource)")
    icon: str | None = Field(None, description="Icon value that was saved")
    flag_ids: list[UUID] = Field(default_factory=list, description="Selected flag option UUIDs")
    active: bool | None = Field(None, description="Echoed persona_active flag state")
    department_ids: list[UUID] = Field(default_factory=list, description="Currently associated department UUIDs")
    example_ids: list[UUID] = Field(default_factory=list, description="Currently associated example resource UUIDs")
    parameter_field_ids: list[UUID] = Field(default_factory=list, description="Currently associated parameter field UUIDs")
    voice_ids: list[UUID] = Field(default_factory=list, description="Currently associated voice resource UUIDs")


class PatchPersonaDraftApiResponse(BaseModel):
    """Response model for new-style persona draft endpoint."""

    success: bool = Field(..., description="Whether the draft operation succeeded")
    draft_id: UUID = Field(..., description="UUID of the created or updated draft")
    idempotency_key: UUID = Field(..., description="Idempotency key for this draft operation (same as draft entry ID)")
    message: str = Field(..., description="Human-readable result message")
    form_state: DraftFormState = Field(..., description="Complete form state after patch — client should replace local state")


# ========== Export Endpoint Types ==========


class ExportPersonaApiRequest(BaseModel):
    """Request model for export persona endpoint."""

    persona_id: UUID | None = Field(None, description="UUID of a specific persona to export (omit for bulk export)")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")

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


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsPersonaApiRequest(BaseModel):
    """Request model for persona generations endpoint."""

    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")
    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")


class GenerationsPersonaListItem(BaseModel):
    """Single generation group in the persona generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsPersonaApiResponse(BaseModel):
    """Response model for persona generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsPersonaListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemPersonaApiRequest(BaseModel):
    """Request model for persona problem endpoint.

    Two body shapes:
      - First call: ``type`` and ``message`` required.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant problem by ``idempotency_key``.
    """

    type: str | None = Field(
        None, description="Problem type: feature, bug, question, other (required on first call)",
    )
    message: str | None = Field(
        None, description="Problem description, max 1000 chars (required on first call)",
    )

    # Ack
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant problem")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ProblemPersonaApiResponse(BaseModel):
    """Response model for persona problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# =============================================================================
# Text Download Types
# =============================================================================


class TextDownloadPersonaApiRequest(BaseModel):
    """Request model for persona text download endpoint."""

    text_id: UUID = Field(..., description="UUID of the texts_resource to download")


class TextDownloadPersonaApiResult(BaseModel):
    """Resolved file info returned by the infra function.

    The transport layer (HTTP/WS) uses this to serve the file appropriately.
    """

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


# =============================================================================
# Call Download Types
# =============================================================================


class CallDownloadPersonaApiRequest(BaseModel):
    """Request model for persona call download endpoint."""

    call_id: UUID = Field(..., description="UUID of the calls_resource to download")


class CallDownloadPersonaApiResult(BaseModel):
    """Resolved call file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")
