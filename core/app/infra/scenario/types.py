"""Scenario API types - handcrafted types for scenario endpoints.

These types are used for the scenario API endpoints and include
Python-computed permissions and UI flags.
"""

from datetime import datetime
from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.api_types import ListFilterSection
from app.infra.persona.types import ImportField, SectionFilter
from app.infra.resource_type_filter import ScopedItem
from app.tools.entries.scenario_drafts.types import GetScenarioDraftResponse

# =============================================================================
# Resource Types
# =============================================================================


class ScenarioNameResource(BaseModel):
    """Name resource for scenario."""

    id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Display name")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    selected: bool = False
    suggested: bool = False
    pending: bool = False


class ScenarioDescriptionResource(BaseModel):
    """Description resource for scenario."""

    id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    selected: bool = False
    suggested: bool = False
    pending: bool = False


class ScenarioFlagResource(BaseModel):
    """Flag option row — one per (name, type, value) entry in flags_resource."""

    id: UUID | None = Field(None, description="Flag resource identifier")
    name: str | None = Field(None, description="Flag display name")
    type: str | None = Field(None, description="Flag type (e.g. 'scenario_active')")
    value: bool | None = Field(None, description="Underlying bool value of this option")
    description: str | None = Field(None, description="Flag description text")
    icon_id: UUID | None = Field(None, description="Icon identifier for the flag")
    icon: str | None = Field(None, description="Resolved SVG markup (hydrated from icons_resource)")
    generated: bool | None = Field(None, description="Whether the flag was AI-generated")
    suggested: bool = Field(False, description="Whether this item is suggested")
    selected: bool = Field(False, description="Whether this item is selected")
    pending: bool = Field(False, description="Whether this item is pending acceptance")


class ScenarioDepartment(BaseModel):
    """Department for scenario."""

    department_id: UUID | None = Field(None, description="UUID of the department")
    name: str | None = Field(None, description="Department name")
    description: str | None = Field(None, description="Department description text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    selected: bool = False
    suggested: bool = False
    pending: bool = False


class ScenarioPersona(BaseModel):
    """Persona for scenario."""

    persona_id: UUID | None = Field(None, description="UUID of the persona")
    name: str | None = Field(None, description="Persona name")
    description: str | None = Field(None, description="Persona description text")
    color: str | None = Field(None, description="Display color for the persona")
    icon: str | None = Field(None, description="Icon identifier for the persona")
    image_model: bool | None = Field(None, description="Whether this persona uses an image model")
    parameter_ids: list[UUID] | None = Field(None, description="Linked parameter UUIDs")
    field_ids: list[UUID] | None = Field(None, description="Linked field UUIDs")
    example: str | None = Field(None, description="Example text for the persona")
    video_persona: bool | None = Field(None, description="Has linked parameter with video enabled")
    non_video_persona: bool | None = Field(
        None, description="Has linked parameter with video disabled"
    )
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    selected: bool = False
    suggested: bool = False
    pending: bool = False


class ScenarioObjective(BaseModel):
    """Objective for scenario."""

    id: UUID | None = Field(None, description="UUID of the objective")
    objective: str | None = Field(None, description="Objective text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    selected: bool = False
    suggested: bool = False
    pending: bool = False


class ScenarioDocument(BaseModel):
    """Document for scenario."""

    document_id: UUID | None = Field(None, description="UUID of the document")
    name: str | None = Field(None, description="Document name")
    description: str | None = Field(None, description="Document description text")
    file_id: UUID | None = Field(None, description="UUID of the files_resource (used for download)")
    file_path: str | None = Field(None, description="Storage path of the file")
    mime_type: str | None = Field(None, description="MIME type of the document")
    upload_id: UUID | None = Field(None, description="UUID of the associated upload")
    html: bool | None = Field(None, description="Whether the document is HTML content")
    parameter_ids: list[UUID] | None = Field(None, description="Linked parameter UUIDs")
    field_ids: list[UUID] | None = Field(None, description="Linked field UUIDs")
    parent_document_id: UUID | None = Field(None, description="UUID of the parent document")
    video_document: bool | None = Field(None, description="Has linked parameter with video enabled")
    non_video_document: bool | None = Field(
        None, description="Has linked parameter with video disabled"
    )
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    selected: bool = False
    suggested: bool = False
    pending: bool = False


class ScenarioParameter(BaseModel):
    """Parameter for scenario."""

    parameter_id: UUID | None = Field(None, description="UUID of the parameter")
    name: str | None = Field(None, description="Parameter name")
    description: str | None = Field(None, description="Parameter description text")
    document_parameter: bool | None = Field(None, description="Whether this is a document parameter")
    persona_parameter: bool | None = Field(None, description="Whether this is a persona parameter")
    scenario_parameter: bool | None = Field(None, description="Whether this is a scenario parameter")
    video_parameter: bool | None = Field(None, description="Whether this is a video parameter")
    non_video_parameter: bool | None = Field(
        None, description="Inverse of video_parameter for frontend filtering"
    )
    conditional: bool | None = Field(None, description="Whether this parameter is conditional")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    selected: bool = False
    suggested: bool = False
    pending: bool = False


class ScenarioField(BaseModel):
    """Field for scenario."""

    id: UUID | None = Field(None, description="UUID of the parameter_fields_resource junction row; required by the client picker to select a field")
    field_id: UUID | None = Field(None, description="UUID of the field")
    name: str | None = Field(None, description="Field name")
    description: str | None = Field(None, description="Field description text")
    parameter_id: UUID | None = Field(None, description="UUID of the linked parameter")
    parameter_name: str | None = Field(None, description="Name of the linked parameter")
    conditional_parameter_ids: list[UUID] | None = Field(None, description="Conditional parameter UUIDs")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    selected: bool = False
    suggested: bool = False
    pending: bool = False


class ScenarioImage(BaseModel):
    """Image for scenario."""

    image_id: UUID | None = Field(None, description="UUID of the image")
    name: str | None = Field(None, description="Image name")
    file_path: str | None = Field(None, description="Storage path of the image file")
    mime_type: str | None = Field(None, description="MIME type of the image")
    upload_id: UUID | None = Field(None, description="UUID of the associated upload")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    selected: bool = False
    suggested: bool = False
    pending: bool = False


class ScenarioVideo(BaseModel):
    """Video for scenario."""

    video_id: UUID | None = Field(None, description="UUID of the video")
    name: str | None = Field(None, description="Video name")
    file_path: str | None = Field(None, description="Storage path of the video file")
    mime_type: str | None = Field(None, description="MIME type of the video")
    upload_id: UUID | None = Field(None, description="UUID of the associated upload")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    selected: bool = False
    suggested: bool = False
    pending: bool = False


class ScenarioQuestion(BaseModel):
    """Question for scenario."""

    question_id: UUID | None = Field(None, description="UUID of the question")
    question_text: str | None = Field(None, description="Question text content")
    allow_multiple: bool | None = Field(None, description="Whether multiple answers are allowed")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    selected: bool = False
    suggested: bool = False
    pending: bool = False


class ScenarioOption(BaseModel):
    """Option for scenario."""

    option_id: UUID | None = Field(None, description="UUID of the option")
    option_text: str | None = Field(None, description="Option text content")
    is_correct: bool | None = Field(None, description="Whether this is the correct option")
    question_id: UUID | None = Field(None, description="UUID of the parent question")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    selected: bool = False
    suggested: bool = False
    pending: bool = False


class ScenarioProblemStatement(BaseModel):
    """Problem statement for scenario."""

    problem_statement_id: UUID | None = Field(None, description="UUID of the problem statement")
    name: str | None = Field(None, description="Problem statement name")
    problem_statement: str | None = Field(None, description="Problem statement text")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    selected: bool = False
    suggested: bool = False
    pending: bool = False


class ScenarioFieldParamFilter(BaseModel):
    """Field parameter filter for show_selected filtering."""

    parameter_id: UUID | None = Field(None, description="UUID of the parameter to filter by")
    show_selected: bool | None = Field(None, description="Whether to show only selected items")


# =============================================================================
# Resource Bucket Types (for three-layer architecture)
# =============================================================================


class ScenarioResourceBucket(BaseModel):
    """Generic resources bucket with full objects (always plural lists)."""

    names: list[ScenarioNameResource] | None = Field(None, description="List of name resources")
    descriptions: list[ScenarioDescriptionResource] | None = Field(None, description="List of description resources")
    problem_statements: list[ScenarioProblemStatement] | None = Field(None, description="List of problem statement resources")
    flags: list[ScenarioFlagResource] | None = Field(None, description="List of flag configs")
    departments: list[ScenarioDepartment] | None = Field(None, description="List of department resources")
    personas: list[ScenarioPersona] | None = Field(None, description="List of persona resources")
    documents: list[ScenarioDocument] | None = Field(None, description="List of document resources")
    parameters: list[ScenarioParameter] | None = Field(None, description="List of parameter resources")
    parameter_fields: list[ScenarioField] | None = Field(None, description="List of parameter field resources")
    objectives: list[ScenarioObjective] | None = Field(None, description="List of objective resources")
    images: list[ScenarioImage] | None = Field(None, description="List of image resources")
    videos: list[ScenarioVideo] | None = Field(None, description="List of video resources")
    questions: list[ScenarioQuestion] | None = Field(None, description="List of question resources")
    options: list[ScenarioOption] | None = Field(None, description="List of option resources")


class ScenarioResources(BaseModel):
    """Full resources + current selections."""

    resources: ScenarioResourceBucket | None = Field(None, description="All available resources")
    current: ScenarioResourceBucket | None = Field(None, description="Currently selected resources")


# =============================================================================
# GET Endpoint Types
# =============================================================================


class GetScenarioApiRequest(BaseModel):
    """Request for getting a single scenario."""

    id: UUID | None = Field(None, description="UUID of the scenario to retrieve")
    draft_id: UUID | None = Field(None, description="UUID of the draft")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")
    # Per-section filters
    names: SectionFilter | None = None
    descriptions: SectionFilter | None = None
    problem_statements: SectionFilter | None = None
    flags: SectionFilter | None = None
    departments: SectionFilter | None = None
    personas: SectionFilter | None = None
    documents: SectionFilter | None = None
    parameters: SectionFilter | None = None
    parameter_fields: SectionFilter | None = None
    objectives: SectionFilter | None = None
    images: SectionFilter | None = None
    videos: SectionFilter | None = None
    questions: SectionFilter | None = None
    options: SectionFilter | None = None


class GetScenarioApiResponse(BaseModel):
    """Response for getting a single scenario."""

    # Context
    actor_name: str | None = Field(None, description="Display name of the current actor")
    scenario_exists: bool | None = Field(None, description="Whether the scenario exists")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    disabled_reason: str | None = Field(None, description="Reason the scenario is disabled")
    group_id: UUID | None = Field(None, description="UUID of the owning group")
    draft_name: str | None = Field(
        None,
        description="Immutable draft label from the active draft entry, when a "
        "``draft_id`` was supplied. ``None`` for non-draft fetches.",
    )

    # AI generation flag (user has draft permission)
    show_ai_generate: bool | None = Field(None, description="Whether AI generation is available")

    # Resolved parameter IDs (derived from saved parameter_fields)
    resolved_parameter_ids: list[str] | None = Field(None, description="Resolved parameter IDs from saved fields")

    # Per-resource lists
    names: list[ScenarioNameResource] | None = Field(None, description="Name resources")
    descriptions: list[ScenarioDescriptionResource] | None = Field(None, description="Description resources")
    problem_statements: list[ScenarioProblemStatement] | None = Field(None, description="Problem statement resources")
    flags: list[ScenarioFlagResource] | None = Field(None, description="Flag configs")
    departments: list[ScenarioDepartment] | None = Field(None, description="Department resources")
    personas: list[ScenarioPersona] | None = Field(None, description="Persona resources")
    documents: list[ScenarioDocument] | None = Field(None, description="Document resources")
    parameters: list | None = Field(None, description="Parameter resources")
    parameter_fields: list[ScenarioField] | None = Field(None, description="Parameter field resources")
    objectives: list[ScenarioObjective] | None = Field(None, description="Objective resources")
    images: list[ScenarioImage] | None = Field(None, description="Image resources")
    videos: list[ScenarioVideo] | None = Field(None, description="Video resources")
    questions: list[ScenarioQuestion] | None = Field(None, description="Question resources")
    options: list[ScenarioOption] | None = Field(None, description="Option resources")


# =============================================================================
# LIST Endpoint Types
# =============================================================================


class ListScenarioApiScenario(BaseModel):
    """Scenario item in list response with Python-computed permissions."""

    id: UUID | None = Field(None, description="Scenario artifact UUID (canonical id; mirrors scenario_id)")
    scenario_id: UUID | None = Field(None, description="UUID of the scenario")
    name: str | None = Field(None, description="Display name")
    problem_statement: str | None = Field(None, description="Problem statement text")
    is_inactive: bool | None = Field(None, description="Whether the scenario is inactive")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    mcp: bool | None = Field(None, description="Whether this is an MCP scenario")
    department_ids: list[str] | None = Field(None, description="Associated department UUIDs")
    objective_ids: list[str] | None = Field(None, description="Associated objective UUIDs")
    persona_ids: list[str] | None = Field(None, description="Associated persona UUIDs")
    field_ids: list[str] | None = Field(None, description="Associated field UUIDs")
    simulation_ids: list[str] | None = Field(None, description="Associated simulation UUIDs")
    num_simulations: int | None = Field(None, description="Total number of simulations")
    active_simulation_count: int | None = Field(None, description="Number of active simulations")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    can_delete: bool | None = Field(None, description="Whether the current user can delete")
    can_duplicate: bool | None = Field(None, description="Whether the current user can duplicate")
    cohort_ids: list[str] | None = Field(None, description="Associated cohort UUIDs")
    # Soft-call ledger snapshot — set when this scenario has a pending op
    # in ``soft_calls_mv``. Client renders ghost/pending styling when set.
    pending_status: str | None = Field(None, description="Latest soft_calls_mv status: 'pending' / 'accepted' / 'rejected'")
    pending_operation: str | None = Field(None, description="Operation type ('create'|'update'|'delete'|'duplicate') of the pending op")
    pending_call_id: UUID | None = Field(None, description="call_id (idempotency key for ack) of the pending op")
    updated_at: datetime | None = Field(None, description="Last updated timestamp")


class ListScenarioApiObjective(BaseModel):
    """Objective in list response."""

    objective_id: str | None = Field(None, description="UUID of the objective")
    name: str | None = Field(None, description="Objective name")
    description: str | None = Field(None, description="Objective description text")


class ListScenarioApiField(BaseModel):
    """Field in list response."""

    field_id: str | None = Field(None, description="UUID of the field")
    name: str | None = Field(None, description="Field name")
    description: str | None = Field(None, description="Field description text")


class ListScenarioApiCohort(BaseModel):
    """Cohort in list response."""

    cohort_id: str | None = Field(None, description="UUID of the cohort")
    name: str | None = Field(None, description="Cohort name")
    description: str | None = Field(None, description="Cohort description text")


class ListScenarioApiPersona(BaseModel):
    """Persona in list response."""

    persona_id: str | None = Field(None, description="UUID of the persona")
    name: str | None = Field(None, description="Persona name")
    description: str | None = Field(None, description="Persona description text")
    color: str | None = Field(None, description="Display color for the persona")
    icon: str | None = Field(None, description="Icon identifier for the persona")


class ListScenarioApiSimulation(BaseModel):
    """Simulation in list response."""

    simulation_id: str | None = Field(None, description="UUID of the simulation")
    name: str | None = Field(None, description="Simulation name")
    description: str | None = Field(None, description="Simulation description text")
    department_ids: list[str] | None = Field(None, description="Associated department UUIDs")


class ListScenarioApiDepartment(BaseModel):
    """Department in list response."""

    department_id: str | None = Field(None, description="UUID of the department")
    name: str | None = Field(None, description="Department name")
    description: str | None = Field(None, description="Department description text")


class ListScenarioApiResponse(BaseModel):
    """Response for listing scenarios."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    scenarios: list[ListScenarioApiScenario] | None = Field(None, description="List of scenario items")
    objectives: list[ListScenarioApiObjective] | None = Field(None, description="List of objective items")
    fields: list[ListScenarioApiField] | None = Field(None, description="List of field items")
    cohorts: list[ListScenarioApiCohort] | None = Field(None, description="List of cohort items")
    personas: list[ListScenarioApiPersona] | None = Field(None, description="List of persona items")
    simulations: list[ListScenarioApiSimulation] | None = Field(None, description="List of simulation items")
    departments: list[ListScenarioApiDepartment] | None = Field(None, description="List of department items")
    persona_filter: "ListFilterSection | None" = Field(None, description="Filter options for personas")
    simulation_filter: "ListFilterSection | None" = Field(None, description="Filter options for simulations")
    department_filter: "ListFilterSection | None" = Field(None, description="Filter options for departments")
    flag_filter: "ListFilterSection | None" = Field(None, description="Filter options for flags")
    total_count: int | None = Field(None, description="Total number of matching records")
    import_fields: list[ImportField] | None = Field(
        None, description="CSV import column schema for the bulk-import dialog"
    )


# =============================================================================
# Shared Save/Create/Update Types
# =============================================================================


class ScenarioFieldError(BaseModel):
    """Per-field error from value resolution."""

    field: str = Field(..., description="Name of the field with the error")
    message: str = Field(..., description="Human-readable error message")


class ScenarioResultItem(BaseModel):
    """Per-item result within a bulk create/update response."""

    success: bool = Field(..., description="Whether the operation succeeded")
    scenario_id: UUID | None = Field(None, description="UUID of the affected scenario")
    message: str = Field(..., description="Human-readable result message")
    errors: list[ScenarioFieldError] | None = Field(None, description="List of per-field errors")


# =============================================================================
# Create Endpoint Types
# =============================================================================


class CreateScenarioItem(ScopedItem):
    """Single scenario item for create — no scenario_id.

    Required fields (name): provide ID or value.
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name_id": "names",
        "name": "names",
        "description_id": "descriptions",
        "description": "descriptions",
        "problem_statement_id": "problem_statements",
        "problem_statement": "problem_statements",
        "flag_ids": "flags",
        "department_ids": "departments",
        "departments": "departments",
        "persona_ids": "personas",
        "personas": "personas",
        "document_ids": "documents",
        "documents": "documents",
        "parameter_ids": "parameters",
        "parameter_field_ids": "parameter_fields",
        "parameter_fields": "parameter_fields",
        "image_ids": "images",
        "images": "images",
        "objective_ids": "objectives",
        "objectives": "objectives",
        "video_ids": "videos",
        "videos": "videos",
        "question_ids": "questions",
        "questions": "questions",
        "option_ids": "options",
        "options": "options",
    }

    id: UUID | None = Field(None, description="Client-provided UUID for the scenario")
    resource_id: UUID | None = Field(None, description="Optional preset UUID for the resource snapshot")

    # Dual-mode: provide ID or raw value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Display name value")
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description text value")
    problem_statement_id: UUID | None = Field(None, description="UUID of the problem statement resource")
    problem_statement: str | None = Field(None, description="Problem statement text value")
    # Canonical flag list — server derives semantics by flag type/value
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    # Multi-select resource IDs
    department_ids: list[UUID] | None = Field(None, description="Associated department UUIDs")
    persona_ids: list[UUID] | None = Field(None, description="Associated persona UUIDs")
    document_ids: list[UUID] | None = Field(None, description="Associated document UUIDs")
    parameter_ids: list[UUID] | None = Field(None, description="Associated parameter UUIDs")
    parameter_field_ids: list[UUID] | None = Field(None, description="Associated parameter field UUIDs")
    image_ids: list[UUID] | None = Field(None, description="Associated image UUIDs")
    objective_ids: list[UUID] | None = Field(None, description="Associated objective UUIDs")
    video_ids: list[UUID] | None = Field(None, description="Associated video UUIDs")
    question_ids: list[UUID] | None = Field(None, description="Associated question UUIDs")
    option_ids: list[UUID] | None = Field(None, description="Associated option UUIDs")
    # Value-based fields for CSV import (resolved to IDs server-side)
    departments: list[str] | None = Field(None, description="Department names for matching")
    personas: list[str] | None = Field(None, description="Persona names for matching")
    documents: list[str] | None = Field(None, description="Document names for matching")
    parameter_fields: list[str] | None = Field(None, description="Parameter field names for matching")
    objectives: list[str] | None = Field(None, description="Objective texts for matching")
    images: list[str] | None = Field(None, description="Image names for matching")
    videos: list[str] | None = Field(None, description="Video names for matching")
    questions: list[str] | None = Field(None, description="Question texts for matching")
    options: list[str] | None = Field(None, description="Option texts for matching")


class CreateScenarioApiRequest(BaseModel):
    """Request model for bulk create scenario endpoint."""

    scenarios: list[CreateScenarioItem] = Field(..., description="List of scenarios to create")

    # Ack
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant create")
    soft: bool = Field(False, description="Stage the create dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class CreateScenarioApiResponse(BaseModel):
    """Response model for bulk create scenario endpoint."""

    results: list[ScenarioResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
    scenarios: list[ListScenarioApiScenario] | None = Field(
        None, description="Hydrated rows for the successfully-created scenarios (mirrors /scenario/search shape)",
    )


# =============================================================================
# Update Endpoint Types
# =============================================================================


class UpdateScenarioItem(ScopedItem):
    """Single scenario item for update — scenario_id required, all fields optional.

    Only provided fields are updated (partial update).
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = CreateScenarioItem.RESOURCE_TYPE_MAP

    id: UUID = Field(..., description="UUID of the scenario to update")
    # Dual-mode: provide ID or raw value
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    name: str | None = Field(None, description="Display name value")
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    description: str | None = Field(None, description="Description text value")
    problem_statement_id: UUID | None = Field(None, description="UUID of the problem statement resource")
    problem_statement: str | None = Field(None, description="Problem statement text value")
    # Canonical flag list — server derives semantics by flag type/value
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    # Multi-select resource IDs
    department_ids: list[UUID] | None = Field(None, description="Associated department UUIDs")
    persona_ids: list[UUID] | None = Field(None, description="Associated persona UUIDs")
    document_ids: list[UUID] | None = Field(None, description="Associated document UUIDs")
    parameter_ids: list[UUID] | None = Field(None, description="Associated parameter UUIDs")
    parameter_field_ids: list[UUID] | None = Field(None, description="Associated parameter field UUIDs")
    image_ids: list[UUID] | None = Field(None, description="Associated image UUIDs")
    objective_ids: list[UUID] | None = Field(None, description="Associated objective UUIDs")
    video_ids: list[UUID] | None = Field(None, description="Associated video UUIDs")
    question_ids: list[UUID] | None = Field(None, description="Associated question UUIDs")
    option_ids: list[UUID] | None = Field(None, description="Associated option UUIDs")
    # Value-based fields for CSV import (resolved to IDs server-side)
    departments: list[str] | None = Field(None, description="Department names for matching")
    personas: list[str] | None = Field(None, description="Persona names for matching")
    documents: list[str] | None = Field(None, description="Document names for matching")
    parameter_fields: list[str] | None = Field(None, description="Parameter field names for matching")
    objectives: list[str] | None = Field(None, description="Objective texts for matching")
    images: list[str] | None = Field(None, description="Image names for matching")
    videos: list[str] | None = Field(None, description="Video names for matching")
    questions: list[str] | None = Field(None, description="Question texts for matching")
    options: list[str] | None = Field(None, description="Option texts for matching")


class UpdateScenarioPatch(UpdateScenarioItem):
    """Shared patch for bulk-update-all-matching mode.

    Inherits every field from ``UpdateScenarioItem`` and just relaxes
    ``id`` to optional — the bulk impl stamps the resolved id onto a
    clone of the patch per matched row, so any client-supplied id is
    ignored. Sparse semantics: only fields the client sets are written.
    """

    id: UUID | None = Field(  # type: ignore[assignment]
        None,
        description="Ignored — bulk impl stamps the resolved scenario id per matched row",
    )


class UpdateScenarioApiRequest(BaseModel):
    """Request model for bulk update scenario endpoint.

    Three body shapes:
      - First call (explicit): ``scenarios`` required — per-row patches.
      - First call (all-matching): ``all=true`` plus the filter fields
        ``/scenario/search`` accepts plus a single shared ``patch`` that
        every matched row receives. The impl resolves matching ids,
        subtracts ``excluded_ids``, and runs the existing per-row
        update flow with the patch cloned per id.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant update by ``idempotency_key``.
    """

    scenarios: list[UpdateScenarioItem] | None = Field(
        None, description="List of scenarios to update (required on first call when ``all`` is false)",
    )

    # All-matching path. Same shape as DeleteScenarioApiRequest; ``patch``
    # is the shared change set applied to every matched row. ``patch.id``
    # is ignored — each resolved id is stamped onto a clone before the
    # per-row update fires.
    all: bool | None = Field(False, description="When true, apply ``patch`` to every scenario matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    patch: UpdateScenarioPatch | None = Field(None, description="Shared change set applied to every matched row when ``all=true`` (sparse — only set fields are updated; ``patch.id`` ignored)")
    search: str | None = Field(None, description="Full-text search query")
    persona_ids: list[UUID] | None = Field(None, description="Filter by persona UUIDs")
    simulation_ids: list[UUID] | None = Field(None, description="Filter by simulation UUIDs")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    persona_search: str | None = Field(None, description="Search text for persona facet (no-op for row filtering)")
    simulation_search: str | None = Field(None, description="Search text for simulation facet (no-op for row filtering)")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    flag_search: str | None = Field(None, description="Search text for flag facet (no-op for row filtering)")

    # Ack
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant update")
    soft: bool = Field(False, description="Stage the update dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class UpdateScenarioApiResponse(BaseModel):
    """Response model for bulk update scenario endpoint."""

    results: list[ScenarioResultItem] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
    scenarios: list[ListScenarioApiScenario] | None = Field(
        None, description="Hydrated rows for the successfully-updated scenarios (mirrors /scenario/search shape)",
    )


class SaveScenarioFieldError(BaseModel):
    """Per-field validation error."""

    field: str = Field(..., description="Name of the field with the error")
    message: str = Field(..., description="Human-readable error message")


# =============================================================================
# EXPORT Endpoint Types
# =============================================================================


class ExportScenarioApiRequest(BaseModel):
    """Request model for export scenario endpoint."""

    scenario_id: UUID | None = Field(None, description="UUID of the scenario to export")

    search: str | None = Field(None, description="Search query text")
    persona_ids: list[str] | None = Field(None, description="Filter by persona UUIDs")
    simulation_ids: list[str] | None = Field(None, description="Filter by simulation UUIDs")
    filter_department_ids: list[str] | None = Field(None, description="Filter by department UUIDs")
    idempotency_key: UUID | None = Field(None, description="Idempotency key — replays the prior export instead of re-running")


class ExportScenarioApiResponse(BaseModel):
    """Response model for export scenario endpoint."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Suggested file name for download")
    mime_type: str = Field(..., description="MIME type of the exported content")
    row_count: int = Field(..., description="Total number of exported rows")


# =============================================================================
# DELETE Endpoint Types
# =============================================================================


class DeleteScenarioApiRequest(BaseModel):
    """Request model for bulk delete scenario endpoint.

    Three body shapes:
      - First call (explicit): ``scenario_ids`` required.
      - First call (all-matching): ``all=true`` plus the same filter
        fields ``/scenario/search`` accepts. The impl resolves every
        matching id server-side, subtracts ``excluded_ids``, and runs
        the existing per-row delete flow.
      - Ack call: ``{idempotency_key, accept}`` only — the impl locates
        the dormant deletion by ``idempotency_key``.
    """

    scenario_ids: list[UUID] | None = Field(
        None, description="UUIDs of scenarios to delete (required on first call when ``all`` is false)",
    )

    # All-matching path. Field names mirror ``SearchScenarioApiRequest``
    # so the client can pass URL-backed nuqs filter state through to a
    # bulk delete unchanged. Independent class (not a shared "filter"
    # sub-model) so future divergence from search predicates is trivial.
    all: bool | None = Field(False, description="When true, delete every scenario matching the filter fields below (minus ``excluded_ids``)")
    excluded_ids: list[UUID] | None = Field(None, description="UUIDs to skip even when matched by ``all``-mode filters")
    # Filter fields (same shape as /scenario/search). Only meaningful
    # when ``all=true``; the validator does not enforce that today —
    # the impl simply ignores them when ``scenario_ids`` is set.
    search: str | None = Field(None, description="Full-text search query")
    persona_ids: list[UUID] | None = Field(None, description="Filter by persona UUIDs")
    simulation_ids: list[UUID] | None = Field(None, description="Filter by simulation UUIDs")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    persona_search: str | None = Field(None, description="Search text for persona facet (no-op for row filtering)")
    simulation_search: str | None = Field(None, description="Search text for simulation facet (no-op for row filtering)")
    department_search: str | None = Field(None, description="Search text for department facet (no-op for row filtering)")
    flag_search: str | None = Field(None, description="Search text for flag facet (no-op for row filtering)")

    # Ack
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — confirms or rejects a dormant delete")
    soft: bool = Field(False, description="Stage the delete dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (confirm deletion) or reject (restore). Only meaningful with idempotency_key")


class DeleteScenarioResult(BaseModel):
    """Per-item result from bulk delete."""

    success: bool = Field(False, description="Whether the operation succeeded")
    scenario_id: UUID | None = Field(None, description="UUID of the deleted scenario")
    message: str | None = Field(None, description="Human-readable result message")


class DeleteScenarioApiResponse(BaseModel):
    """Bulk delete response."""

    results: list[DeleteScenarioResult] = Field(..., description="List of operation results")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")


# =============================================================================
# DUPLICATE Endpoint Types
# =============================================================================


class DuplicateScenarioApiRequest(BaseModel):
    """Request for duplicating a scenario."""

    scenario_id: UUID = Field(..., description="UUID of the scenario to duplicate")

    # Ack
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant duplicate")
    soft: bool = Field(False, description="Stage the duplicate dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class DuplicateScenarioApiResponse(BaseModel):
    """Response for duplicating a scenario."""

    success: bool = Field(..., description="Whether the operation succeeded")
    scenario_id: UUID = Field(..., description="UUID of the duplicated scenario")
    message: str = Field(..., description="Human-readable result message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")
    scenarios: list[ListScenarioApiScenario] | None = Field(
        None, description="Hydrated row for the newly-created duplicate scenario (single-element list)",
    )


# =============================================================================
# DRAFT Endpoint Types
# =============================================================================


class DraftObjectiveValue(BaseModel):
    """Value for creating an objective via the draft endpoint."""

    objective: str = Field(..., description="Objective text")


class DraftImageValue(BaseModel):
    """Value for creating an image via the draft endpoint."""

    name: str = Field(..., description="Image name")
    description: str = Field(..., description="Image description text")
    upload_id: UUID | None = Field(
        None, description="UUID of the associated upload"
    )


class DraftVideoValue(BaseModel):
    """Value for creating a video via the draft endpoint."""

    name: str = Field(..., description="Video name")
    description: str = Field(..., description="Video description text")
    upload_id: UUID | None = Field(
        None, description="UUID of the associated upload"
    )
    length_seconds: int = Field(0, description="Video length in seconds")


class DraftQuestionValue(BaseModel):
    """Value for creating a question via the draft endpoint."""

    question_text: str = Field(..., description="Question text content")
    time: int = Field(30, description="Time limit in seconds")
    allow_multiple: bool = Field(False, description="Whether multiple answers are allowed")


class DraftOptionValue(BaseModel):
    """Value for creating an option via the draft endpoint."""

    option_text: str = Field(..., description="Option text content")
    question_id: UUID | None = Field(None, description="UUID of the parent question")


class PatchScenarioDraftApiRequest(ScopedItem):
    """Request model for new-style scenario draft endpoint.

    Dual-mode for creatable resources:
      - Single-select: name/name_id, description/description_id,
        problem_statement/problem_statement_id
      - Multi-select (merged): objectives/objective_ids, images/image_ids,
        videos/video_ids, questions/question_ids, options/option_ids
        (values are created as resources, then IDs are merged with existing IDs)

    ID-only for non-creatable resources:
      - flag_ids, department_ids, persona_ids, document_ids, parameter_field_ids

    Client always sends full state (append-only — each write is a new snapshot).
    """

    RESOURCE_TYPE_MAP: ClassVar[dict[str, str]] = {
        "name": "names",
        "name_id": "names",
        "description": "descriptions",
        "description_id": "descriptions",
        "problem_statement": "problem_statements",
        "problem_statement_id": "problem_statements",
        "objectives": "objectives",
        "objective_ids": "objectives",
        "images": "images",
        "image_ids": "images",
        "videos": "videos",
        "video_ids": "videos",
        "questions": "questions",
        "question_ids": "questions",
        "options": "options",
        "option_ids": "options",
        "flag_ids": "flags",
        "active": "flags",
        "video_enabled": "flags",
        "problem_statement_enabled": "flags",
        "objectives_enabled": "flags",
        "images_enabled": "flags",
        "questions_enabled": "flags",
        "department_ids": "departments",
        "persona_ids": "personas",
        "document_ids": "documents",
        "parameter_field_ids": "parameter_fields",
    }

    input_draft_id: UUID | None = Field(None, description="UUID of the input draft")

    # Creatable single-select — provide value or ID
    name: str | None = Field(None, description="Display name value")
    name_id: UUID | None = Field(None, description="UUID of the name resource")
    description: str | None = Field(None, description="Description text value")
    description_id: UUID | None = Field(None, description="UUID of the description resource")
    problem_statement: str | None = Field(None, description="Problem statement text value")
    problem_statement_id: UUID | None = Field(None, description="UUID of the problem statement resource")

    # Creatable multi-select — values merged with IDs
    objectives: list[str] | None = Field(None, description="Objective texts to create")
    objective_ids: list[UUID] | None = Field(None, description="Existing objective UUIDs")
    images: list[DraftImageValue] | None = Field(None, description="Image values to create")
    image_ids: list[UUID] | None = Field(None, description="Existing image UUIDs")
    videos: list[DraftVideoValue] | None = Field(None, description="Video values to create")
    video_ids: list[UUID] | None = Field(None, description="Existing video UUIDs")
    questions: list[DraftQuestionValue] | None = Field(None, description="Question values to create")
    question_ids: list[UUID] | None = Field(None, description="Existing question UUIDs")
    options: list[DraftOptionValue] | None = Field(None, description="Option values to create")
    option_ids: list[UUID] | None = Field(None, description="Existing option UUIDs")

    # Non-creatable — ID-only
    flag_ids: list[UUID] | None = Field(None, description="Selected flag option UUIDs — canonical; server derives semantics by flag type/value")
    # Denormalized booleans — resolved server-side to flag_ids entries via (type, value) lookup.
    active: bool | None = Field(None, description="Denormalized scenario_active flag state")
    video_enabled: bool | None = Field(None, description="Denormalized video_enabled flag state")
    problem_statement_enabled: bool | None = Field(None, description="Denormalized problem_statement_enabled flag state")
    objectives_enabled: bool | None = Field(None, description="Denormalized objectives_enabled flag state")
    images_enabled: bool | None = Field(None, description="Denormalized images_enabled flag state")
    questions_enabled: bool | None = Field(None, description="Denormalized questions_enabled flag state")
    department_ids: list[UUID] | None = Field(None, description="Associated department UUIDs")
    persona_ids: list[UUID] | None = Field(None, description="Associated persona UUIDs")
    document_ids: list[UUID] | None = Field(None, description="Associated document UUIDs")
    parameter_field_ids: list[UUID] | None = Field(None, description="Associated parameter field UUIDs")

    # Pending state — resource IDs to keep as pending (active=false on connection)
    pending_ids: list[UUID] | None = Field(None, description="Resource IDs to keep as pending (active=false on connection)")

    # Ack
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant draft")
    soft: bool = Field(False, description="Stage the draft dormant (active=False) — propose; the ack ({idempotency_key, accept}) promotes/rejects it")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ScenarioDraftFormState(BaseModel):
    """Full form state after draft patch — server is source of truth.

    Client replaces its local form state with this after every successful patch.
    """

    name_id: UUID | None = Field(None, description="UUID of the selected name resource")
    description_id: UUID | None = Field(None, description="UUID of the selected description resource")
    problem_statement_id: UUID | None = Field(None, description="UUID of the selected problem statement resource")
    flag_ids: list[UUID] = Field([], description="Selected flag UUIDs")
    active: bool | None = Field(None, description="Echoed scenario_active flag state")
    video_enabled: bool | None = Field(None, description="Echoed video_enabled flag state")
    problem_statement_enabled: bool | None = Field(None, description="Echoed problem_statement_enabled flag state")
    objectives_enabled: bool | None = Field(None, description="Echoed objectives_enabled flag state")
    images_enabled: bool | None = Field(None, description="Echoed images_enabled flag state")
    questions_enabled: bool | None = Field(None, description="Echoed questions_enabled flag state")
    department_ids: list[UUID] = Field([], description="Selected department UUIDs")
    persona_ids: list[UUID] = Field([], description="Selected persona UUIDs")
    document_ids: list[UUID] = Field([], description="Selected document UUIDs")
    parameter_field_ids: list[UUID] = Field([], description="Selected parameter field UUIDs")
    objective_ids: list[UUID] = Field([], description="Selected objective UUIDs")
    image_ids: list[UUID] = Field([], description="Selected image UUIDs")
    video_ids: list[UUID] = Field([], description="Selected video UUIDs")
    question_ids: list[UUID] = Field([], description="Selected question UUIDs")
    option_ids: list[UUID] = Field([], description="Selected option UUIDs")


class PatchScenarioDraftApiResponse(BaseModel):
    """Response model for new-style scenario draft endpoint."""

    success: bool = Field(..., description="Whether the operation succeeded")
    draft_id: UUID = Field(..., description="UUID of the saved draft")
    idempotency_key: UUID = Field(..., description="Idempotency key for this draft operation (same as draft entry ID)")
    message: str = Field(..., description="Human-readable result message")
    form_state: ScenarioDraftFormState = Field(..., description="Server-authoritative form state")


class GetScenarioDraftsApiRequest(BaseModel):
    """Request model for the scenario drafts list endpoint.

    Mirrors ``GenerationsScenarioApiRequest`` — name search +
    date window + pagination. All fields optional; an empty body
    returns the caller's most recent drafts.
    """

    search: str | None = Field(None, description="Name search (ILIKE substring)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=200, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")


class GetScenarioDraftsApiResponse(BaseModel):
    """Response model for scenario drafts list endpoint."""

    entries: list[GetScenarioDraftResponse] | None = Field(None, description="List of scenario draft entries")


# =============================================================================
# Image Upload Types
# =============================================================================


class ImageUploadScenarioApiResponse(BaseModel):
    """Response model for scenario image upload endpoint."""

    image_id: UUID = Field(..., description="UUID of the created images_resource")
    upload_id: UUID = Field(..., description="UUID of the uploads_entry (file on disk)")
    idempotency_key: UUID | None = Field(None, description="Server-minted soft-call key; echo with accept to promote/reject the staged upload.")


class ImageDownloadScenarioApiRequest(BaseModel):
    """Request model for scenario image download endpoint."""

    image_id: UUID = Field(..., description="UUID of the images_resource to download")


class ImageDownloadScenarioApiResult(BaseModel):
    """Resolved file info returned by the infra function.

    The transport layer (HTTP/WS) uses this to serve the file appropriately.
    """

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


# =============================================================================
# Video Upload/Download Types
# =============================================================================


class VideoUploadScenarioApiResponse(BaseModel):
    """Response model for scenario video upload endpoint."""

    video_id: UUID = Field(..., description="UUID of the created videos_resource")
    upload_id: UUID = Field(..., description="UUID of the uploads_entry (file on disk)")
    idempotency_key: UUID | None = Field(None, description="Server-minted soft-call key; echo with accept to promote/reject the staged upload.")


class VideoDownloadScenarioApiRequest(BaseModel):
    """Request model for scenario video download endpoint."""

    video_id: UUID = Field(..., description="UUID of the videos_resource to download")


class VideoDownloadScenarioApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


# =============================================================================
# Text Download Types
# =============================================================================


class TextDownloadScenarioApiRequest(BaseModel):
    """Request model for scenario text download endpoint."""

    text_id: UUID = Field(..., description="UUID of the texts_resource to download")


class TextDownloadScenarioApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


# =============================================================================
# File Download/Preview Types
# =============================================================================


class FileDownloadScenarioApiRequest(BaseModel):
    """Request model for scenario file download endpoint."""

    file_id: UUID = Field(..., description="UUID of the files_resource to download")


class FileDownloadScenarioApiResult(BaseModel):
    """Resolved file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")


class FilePreviewScenarioApiRequest(BaseModel):
    """Request model for scenario file preview endpoint."""

    file_id: UUID = Field(..., description="UUID of the files_resource to preview")


class FilePreviewScenarioApiResult(BaseModel):
    """Resolved preview info returned by the infra function.

    preview_bytes contains the PNG image of the first page.
    """

    preview_bytes: bytes = Field(..., description="PNG image bytes of the first page")
    upload_id: UUID = Field(..., description="UUID of the uploads_entry")


# =============================================================================
# SQL Row Types (for internal use)
# =============================================================================


class ListScenarioSqlScenario(BaseModel):
    """Raw scenario from SQL — permissions computed in Python."""

    scenario_id: UUID | None = Field(None, description="UUID of the scenario")
    name: str | None = Field(None, description="Display name")
    problem_statement: str | None = Field(None, description="Problem statement text")
    is_inactive: bool | None = Field(None, description="Whether the scenario is inactive")
    generated: bool | None = Field(None, description="Whether this was AI-generated")
    mcp: bool | None = Field(None, description="Whether this is an MCP scenario")
    department_ids: list[str] | None = Field(None, description="Associated department UUIDs")
    objective_ids: list[str] | None = Field(None, description="Associated objective UUIDs")
    persona_ids: list[str] | None = Field(None, description="Associated persona UUIDs")
    field_ids: list[str] | None = Field(None, description="Associated field UUIDs")
    simulation_ids: list[str] | None = Field(None, description="Associated simulation UUIDs")
    num_simulations: int | None = Field(None, description="Total number of simulations")
    active_simulation_count: int | None = Field(None, description="Number of active simulations")
    cohort_ids: list[str] | None = Field(None, description="Associated cohort UUIDs")
    updated_at: datetime | None = Field(None, description="Last updated timestamp")


class ListScenarioSqlRow(BaseModel):
    """Raw SQL row for list scenarios (mapping arrays hydrated in Python)."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    user_role: str | None = Field(None, description="Role of the current user")
    scenarios: list[ListScenarioSqlScenario] | None = Field(None, description="List of raw scenario records")
    persona_options: list[dict] | None = Field(None, description="Persona filter option data")
    simulation_options: list[dict] | None = Field(None, description="Simulation filter option data")
    department_options: list[dict] | None = Field(None, description="Department filter option data")
    total_count: int | None = Field(None, description="Total number of matching records")


# =============================================================================
# SQL Params Types (for internal use)
# =============================================================================


class GetScenarioSqlParams(BaseModel):
    """SQL parameters for get scenario."""

    profile_id: UUID = Field(..., description="UUID of the requesting profile")
    scenario_id: UUID | None = Field(None, description="UUID of the scenario")
    document_ids: list[UUID] | None = Field(None, description="Filter by document UUIDs")
    problem_statement_ids: list[UUID] | None = Field(None, description="Filter by problem statement UUIDs")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    filter_persona_ids: list[UUID] | None = Field(None, description="Filter by persona UUIDs")
    filter_document_ids: list[UUID] | None = Field(None, description="Filter by document UUIDs")
    filter_parameter_ids: list[UUID] | None = Field(None, description="Filter by parameter UUIDs")
    filter_field_ids: list[UUID] | None = Field(None, description="Filter by field UUIDs")
    persona_search: str | None = Field(None, description="Search text to filter personas")
    document_search: str | None = Field(None, description="Search text to filter documents")
    parameter_search: str | None = Field(None, description="Search text to filter parameters")
    description_search: str | None = Field(None, description="Search text to filter descriptions")
    problem_statement_search: str | None = Field(None, description="Search text to filter problem statements")
    image_search: str | None = Field(None, description="Search text to filter images")
    video_search: str | None = Field(None, description="Search text to filter videos")
    question_search: str | None = Field(None, description="Search text to filter questions")
    option_search: str | None = Field(None, description="Search text to filter options")
    persona_show_selected: bool | None = Field(None, description="Show only selected personas")
    document_show_selected: bool | None = Field(None, description="Show only selected documents")
    parameter_show_selected: bool | None = Field(None, description="Show only selected parameters")
    field_show_selected_by_param: list[ScenarioFieldParamFilter] | None = Field(
        default_factory=list, description="Field-level show_selected filters by parameter"
    )
    draft_id: UUID | None = Field(None, description="UUID of the draft")
    mcp: bool | None = Field(False, description="Whether this is an MCP request")

    def to_tuple(self) -> tuple[Any, ...]:
        """Convert to tuple for SQL execution."""
        field_show_selected_by_param_tuples = [
            (conn.parameter_id, conn.show_selected)
            for conn in (self.field_show_selected_by_param or [])
        ]
        return (
            self.profile_id,
            self.scenario_id,
            self.document_ids,
            self.problem_statement_ids,
            self.filter_department_ids,
            self.filter_persona_ids,
            self.filter_document_ids,
            self.filter_parameter_ids,
            self.filter_field_ids,
            self.persona_search,
            self.document_search,
            self.parameter_search,
            self.description_search,
            self.problem_statement_search,
            self.image_search,
            self.video_search,
            self.question_search,
            self.persona_show_selected,
            self.document_show_selected,
            self.parameter_show_selected,
            field_show_selected_by_param_tuples,
            self.draft_id,
            self.mcp,
        )


class GetScenarioSqlRow(BaseModel):
    """SQL row for get scenario."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    scenario_exists: bool | None = Field(None, description="Whether the scenario exists")
    can_edit: bool | None = Field(None, description="Whether the current user can edit")
    disabled_reason: str | None = Field(None, description="Reason the scenario is disabled")
    group_id: UUID | None = Field(None, description="UUID of the owning group")
    name_id: UUID | None = Field(None, description="UUID of the selected name resource")
    name_resource: ScenarioNameResource | None = Field(None, description="Selected name resource")
    show_name: bool | None = Field(None, description="Whether to show name section")
    name_required: bool | None = Field(None, description="Whether name is required")
    name_suggestions: list[UUID] | None = Field(None, description="Suggested name resource UUIDs")
    names: list[ScenarioNameResource] | None = Field(None, description="Available name resources")
    description_id: UUID | None = Field(None, description="UUID of the selected description resource")
    description_resource: ScenarioDescriptionResource | None = Field(None, description="Selected description resource")
    show_description: bool | None = Field(None, description="Whether to show description section")
    description_required: bool | None = Field(None, description="Whether description is required")
    description_suggestions: list[UUID] | None = Field(None, description="Suggested description resource UUIDs")
    descriptions: list[ScenarioDescriptionResource] | None = Field(None, description="Available description resources")
    problem_statement_id: UUID | None = Field(None, description="UUID of the selected problem statement")
    problem_statement_resource: ScenarioProblemStatement | None = Field(None, description="Selected problem statement resource")
    show_problem_statement: bool | None = Field(None, description="Whether to show problem statement section")
    problem_statement_required: bool | None = Field(None, description="Whether problem statement is required")
    problem_statement_suggestions: list[UUID] | None = Field(None, description="Suggested problem statement UUIDs")
    problem_statements: list[ScenarioProblemStatement] | None = Field(None, description="Available problem statements")
    active_flag_id: UUID | None = Field(None, description="UUID of the active flag option")
    active_flag_resource: ScenarioFlagResource | None = Field(None, description="Active flag resource")
    show_active_flag: bool | None = Field(None, description="Whether to show active flag")
    active_flag_required: bool | None = Field(None, description="Whether active flag is required")
    objectives_enabled_flag_id: UUID | None = Field(None, description="UUID of the objectives enabled flag")
    objectives_enabled_flag_resource: ScenarioFlagResource | None = Field(None, description="Objectives enabled flag resource")
    show_objectives_enabled_flag: bool | None = Field(None, description="Whether to show objectives enabled flag")
    objectives_enabled_flag_required: bool | None = Field(None, description="Whether objectives enabled flag is required")
    images_enabled_flag_id: UUID | None = Field(None, description="UUID of the images enabled flag")
    images_enabled_flag_resource: ScenarioFlagResource | None = Field(None, description="Images enabled flag resource")
    show_images_enabled_flag: bool | None = Field(None, description="Whether to show images enabled flag")
    images_enabled_flag_required: bool | None = Field(None, description="Whether images enabled flag is required")
    video_enabled_flag_id: UUID | None = Field(None, description="UUID of the video enabled flag")
    video_enabled_flag_resource: ScenarioFlagResource | None = Field(None, description="Video enabled flag resource")
    show_video_enabled_flag: bool | None = Field(None, description="Whether to show video enabled flag")
    video_enabled_flag_required: bool | None = Field(None, description="Whether video enabled flag is required")
    questions_enabled_flag_id: UUID | None = Field(None, description="UUID of the questions enabled flag")
    questions_enabled_flag_resource: ScenarioFlagResource | None = Field(None, description="Questions enabled flag resource")
    show_questions_enabled_flag: bool | None = Field(None, description="Whether to show questions enabled flag")
    questions_enabled_flag_required: bool | None = Field(None, description="Whether questions enabled flag is required")
    problem_statement_enabled_flag_id: UUID | None = Field(None, description="UUID of the problem statement enabled flag")
    problem_statement_enabled_flag_resource: ScenarioFlagResource | None = Field(None, description="Problem statement enabled flag resource")
    show_problem_statement_enabled_flag: bool | None = Field(None, description="Whether to show problem statement enabled flag")
    problem_statement_enabled_flag_required: bool | None = Field(None, description="Whether problem statement enabled flag is required")
    department_ids: list[UUID] | None = Field(None, description="Selected department UUIDs")
    department_resources: list[ScenarioDepartment] | None = Field(None, description="Selected department resources")
    show_departments: bool | None = Field(None, description="Whether to show departments section")
    departments_required: bool | None = Field(None, description="Whether departments are required")
    department_suggestions: list[UUID] | None = Field(None, description="Suggested department UUIDs")
    departments: list[ScenarioDepartment] | None = Field(None, description="Available department resources")
    parameter_field_ids: list[UUID] | None = Field(None, description="Selected parameter field UUIDs")
    parameter_field_resources: list[ScenarioField] | None = Field(None, description="Selected parameter field resources")
    show_parameter_fields: bool | None = Field(None, description="Whether to show parameter fields section")
    parameter_fields_required: bool | None = Field(None, description="Whether parameter fields are required")
    parameter_fields: list[ScenarioField] | None = Field(None, description="Available parameter field resources")
    objective_ids: list[UUID] | None = Field(None, description="Selected objective UUIDs")
    objective_resources: list[ScenarioObjective] | None = Field(None, description="Selected objective resources")
    show_objectives: bool | None = Field(None, description="Whether to show objectives section")
    objectives_required: bool | None = Field(None, description="Whether objectives are required")
    objective_suggestions: list[UUID] | None = Field(None, description="Suggested objective UUIDs")
    objectives: list[ScenarioObjective] | None = Field(None, description="Available objective resources")
    image_ids: list[UUID] | None = Field(None, description="Selected image UUIDs")
    image_resources: list[ScenarioImage] | None = Field(None, description="Selected image resources")
    show_images: bool | None = Field(None, description="Whether to show images section")
    images_required: bool | None = Field(None, description="Whether images are required")
    image_suggestions: list[UUID] | None = Field(None, description="Suggested image UUIDs")
    images: list[ScenarioImage] | None = Field(None, description="Available image resources")
    video_ids: list[UUID] | None = Field(None, description="Selected video UUIDs")
    video_resources: list[ScenarioVideo] | None = Field(None, description="Selected video resources")
    show_videos: bool | None = Field(None, description="Whether to show videos section")
    videos_required: bool | None = Field(None, description="Whether videos are required")
    video_suggestions: list[UUID] | None = Field(None, description="Suggested video UUIDs")
    videos: list[ScenarioVideo] | None = Field(None, description="Available video resources")
    question_ids: list[UUID] | None = Field(None, description="Selected question UUIDs")
    question_resources: list[ScenarioQuestion] | None = Field(None, description="Selected question resources")
    show_questions: bool | None = Field(None, description="Whether to show questions section")
    questions_required: bool | None = Field(None, description="Whether questions are required")
    question_suggestions: list[UUID] | None = Field(None, description="Suggested question UUIDs")
    questions: list[ScenarioQuestion] | None = Field(None, description="Available question resources")
    option_ids: list[UUID] | None = Field(None, description="Selected option UUIDs")
    option_resources: list[ScenarioOption] | None = Field(None, description="Selected option resources")
    show_options: bool | None = Field(None, description="Whether to show options section")
    options_required: bool | None = Field(None, description="Whether options are required")
    option_suggestions: list[UUID] | None = Field(None, description="Suggested option UUIDs")
    options: list[ScenarioOption] | None = Field(None, description="Available option resources")
    persona_ids: list[UUID] | None = Field(None, description="Selected persona UUIDs")
    persona_resources: list[ScenarioPersona] | None = Field(None, description="Selected persona resources")
    show_personas: bool | None = Field(None, description="Whether to show personas section")
    personas_required: bool | None = Field(None, description="Whether personas are required")
    persona_suggestions: list[UUID] | None = Field(None, description="Suggested persona UUIDs")
    personas: list[ScenarioPersona] | None = Field(None, description="Available persona resources")
    document_ids: list[UUID] | None = Field(None, description="Selected document UUIDs")
    document_resources: list[ScenarioDocument] | None = Field(None, description="Selected document resources")
    show_documents: bool | None = Field(None, description="Whether to show documents section")
    documents_required: bool | None = Field(None, description="Whether documents are required")
    document_suggestions: list[UUID] | None = Field(None, description="Suggested document UUIDs")
    documents: list[ScenarioDocument] | None = Field(None, description="Available document resources")
    parameter_ids: list[UUID] | None = Field(None, description="Selected parameter UUIDs")
    parameter_resources: list[ScenarioParameter] | None = Field(None, description="Selected parameter resources")
    show_parameters: bool | None = Field(None, description="Whether to show parameters section")
    parameters_required: bool | None = Field(None, description="Whether parameters are required")
    parameter_suggestions: list[UUID] | None = Field(None, description="Suggested parameter UUIDs")
    parameters: list[ScenarioParameter] | None = Field(None, description="Available parameter resources")


class GetScenariosListSqlParams(BaseModel):
    """SQL parameters for list scenarios."""

    profile_id: UUID = Field(..., description="UUID of the requesting profile")
    search: str | None = Field(None, description="Search query text")
    persona_ids: list[UUID] | None = Field(None, description="Filter by persona UUIDs")
    simulation_ids: list[UUID] | None = Field(None, description="Filter by simulation UUIDs")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    persona_search: str | None = Field(None, description="Search text to filter personas")
    simulation_search: str | None = Field(None, description="Search text to filter simulations")
    department_search: str | None = Field(None, description="Search text to filter departments")
    page_size: int | None = Field(10, description="Number of results per page")
    page_offset: int | None = Field(0, description="Pagination offset")

    def to_tuple(self) -> tuple[Any, ...]:
        """Convert to tuple for SQL execution."""
        return (
            self.profile_id,
            self.search,
            self.persona_ids,
            self.simulation_ids,
            self.filter_department_ids,
            self.persona_search,
            self.simulation_search,
            self.department_search,
            self.page_size,
            self.page_offset,
        )


class GetScenariosListApiRequest(BaseModel):
    """Request for listing scenarios."""

    search: str | None = Field(None, description="Search query text")
    persona_ids: list[UUID] | None = Field(None, description="Filter by persona UUIDs")
    simulation_ids: list[UUID] | None = Field(None, description="Filter by simulation UUIDs")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    persona_search: str | None = Field(None, description="Search text to filter personas")
    simulation_search: str | None = Field(None, description="Search text to filter simulations")
    department_search: str | None = Field(None, description="Search text to filter departments")
    page_size: int | None = Field(10, description="Number of results per page")
    page_offset: int | None = Field(0, description="Pagination offset")


class DuplicateScenarioSqlParams(BaseModel):
    """SQL parameters for duplicate scenario."""

    scenario_id: UUID = Field(..., description="UUID of the scenario to duplicate")
    profile_id: UUID = Field(..., description="UUID of the requesting profile")
    group_id: UUID | None = Field(None, description="UUID of the owning group")

    def to_tuple(self) -> tuple[Any, ...]:
        """Convert to tuple for SQL execution."""
        return (
            self.scenario_id,
            self.profile_id,
            self.group_id,
        )


class DuplicateScenarioSqlRow(BaseModel):
    """SQL row for duplicate scenario."""

    scenario_id: UUID | None = Field(None, description="UUID of the duplicated scenario")
    scenario_name: str | None = Field(None, description="Name of the duplicated scenario")
    actor_name: str | None = Field(None, description="Display name of the current actor")


# =============================================================================
# Generations Types
# =============================================================================


class GenerationsScenarioApiRequest(BaseModel):
    """Request model for scenario generations endpoint."""

    search: str | None = Field(None, description="Name search (ILIKE)")
    date_from: datetime | None = Field(None, description="Start date filter")
    date_to: datetime | None = Field(None, description="End date filter")
    page_limit: int = Field(50, ge=1, le=100, description="Maximum items per page")
    page_offset: int = Field(0, ge=0, description="Offset for pagination")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads across related requests")


class GenerationsScenarioListItem(BaseModel):
    """Single generation group in the scenario generations response."""

    group_id: UUID = Field(..., description="UUID of the generation group")
    session_id: UUID | None = Field(None, description="UUID of the parent session")
    group_name: str | None = Field(None, description="Name of the generation group")
    created_at: datetime | None = Field(None, description="Timestamp of the generation")


class GenerationsScenarioApiResponse(BaseModel):
    """Response model for scenario generations endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    items: list[GenerationsScenarioListItem] = Field(default_factory=list, description="Generation groups")
    total_count: int = Field(0, description="Total number of matching generations")


# =============================================================================
# Problem Types
# =============================================================================


class ProblemScenarioApiRequest(BaseModel):
    """Request model for scenario problem endpoint."""

    type: str = Field(..., description="Problem type: feature, bug, question, other")
    message: str = Field(..., description="Problem description (max 1000 chars)")

    # Ack
    idempotency_key: UUID | None = Field(None, description="Operation key for ack — promotes or rejects a dormant problem")
    accept: bool | None = Field(None, description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key")


class ProblemScenarioApiResponse(BaseModel):
    """Response model for scenario problem endpoint."""

    problem_id: UUID = Field(..., description="UUID of the created problem")
    success: bool = Field(True, description="Whether the problem was created")
    message: str = Field("Problem created successfully", description="Status message")
    idempotency_key: UUID | None = Field(None, description="Idempotency key echoed back for client correlation")



# =============================================================================
# Call Download Types
# =============================================================================


class CallDownloadScenarioApiRequest(BaseModel):
    """Request model for scenario call download endpoint."""

    call_id: UUID = Field(..., description="UUID of the calls_resource to download")


class CallDownloadScenarioApiResult(BaseModel):
    """Resolved call file info returned by the infra function."""

    upload_id: UUID = Field(..., description="UUID of the uploads_entry")
    file_path: str = Field(..., description="Absolute path to the file on disk")
    content_type: str = Field(..., description="MIME type of the file")
    filename: str = Field(..., description="Original filename for Content-Disposition")
    size: int = Field(..., description="File size in bytes")
