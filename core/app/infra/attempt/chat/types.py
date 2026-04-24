"""Custom types for unified chat endpoints.

These types define the client-facing API contract for both home and practice
modes via a single `practice: bool` parameter. Internal parameters (mode,
accessible_cohort_ids) are NOT included here - they are injected by Python.

Architecture:
- list.py (ANALYTICAL): Simulation cards + attempt history + filter options
- get.py (OPERATIONAL): Simulations user can take + scenario_ids + rubric data
- bundle.py (BUNDLE): Section-first customization before starting chat
"""

from typing import Any, ClassVar
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.resource_type_filter import ScopedItem

from app.infra.api_types import InternalResponseBase
from app.tools.entries.chat_drafts.types import GetChatDraftResponse

# =============================================================================
# Export Types
# =============================================================================


class GetChatDraftsApiResponse(BaseModel):
    """Response model for chat drafts list endpoint."""

    entries: list[GetChatDraftResponse] | None = Field(None, description="List of chat draft entries")


class ExportChatApiResponse(BaseModel):
    """Response model for chat export."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Name of the exported file")
    mime_type: str = Field(..., description="MIME type of the exported file")
    row_count: int = Field(..., description="Number of rows in the export")


# =============================================================================
# Shared types
# =============================================================================


class RubricMapping(BaseModel):
    """Rubric metadata mapping rubric to its standard groups."""

    rubric_id: UUID = Field(..., description="UUID of the rubric")
    name: str | None = Field(None, description="Name of the rubric")
    standard_group_ids: list[str] | None = Field(None, description="IDs of standard groups in this rubric")


class StandardGroupMapping(BaseModel):
    """Standard group metadata for sidebar/legend."""

    standard_group_id: UUID = Field(..., description="UUID of the standard group")
    name: str | None = Field(None, description="Name of the standard group")
    description: str | None = Field(None, description="Description of the standard group")
    points: int | None = Field(None, description="Total points for the group")
    pass_points: int | None = Field(None, description="Points required to pass")


class StandardMapping(BaseModel):
    """Standard metadata for sidebar/legend."""

    standard_id: UUID = Field(..., description="UUID of the standard")
    standard_group_id: UUID | None = Field(None, description="UUID of the parent standard group")
    name: str | None = Field(None, description="Name of the standard")
    description: str | None = Field(None, description="Description of the standard")
    points: int | None = Field(None, description="Points for the standard")


class FilterOption(BaseModel):
    """Filter option for dropdowns."""

    value: str = Field(..., description="Filter option value")
    label: str | None = Field(None, description="Display label for the option")
    count: int | None = Field(None, description="Number of items matching this option")


# =============================================================================
# LIST endpoint types (ANALYTICAL) - Simulation cards + attempt history
# =============================================================================


class GetChatListRequest(BaseModel):
    """Client API request for chat list (analytical).

    Returns simulation cards with stats AND paginated attempt history.

    Args:
        practice: If True, returns practice data. If False, returns home data.
        start_date: Start date filter (required).
        end_date: End date filter (required).
        cohort_ids: Filter by cohorts.
        department_ids: Filter by departments.
        simulation_ids: Filter by simulations.
        scenario_ids: Filter by scenarios.
        infinite_mode: Filter by infinite mode.
        search: Search string.
        sort_by: Sort field ('date' | 'score' | 'simulation_name').
        sort_order: Sort order ('asc' | 'desc').
        page: Page number (0-indexed).
        page_size: Page size.
        profile_ids: Filter by profiles (practice mode only).
        show_archived: Show archived attempts (practice mode only).
    """

    practice: bool = Field(False, description="Whether to fetch practice data")
    start_date: str = Field(..., description="Start date filter (ISO format)")
    end_date: str = Field(..., description="End date filter (ISO format)")
    cohort_ids: list[UUID] | None = Field(default_factory=list, description="Cohort IDs to filter by")  # type: ignore[arg-type]
    department_ids: list[UUID] | None = Field(default_factory=list, description="Department IDs to filter by")  # type: ignore[arg-type]
    simulation_ids: list[UUID] | None = Field(default_factory=list, description="Simulation IDs to filter by")  # type: ignore[arg-type]
    scenario_ids: list[UUID] | None = Field(default_factory=list, description="Scenario IDs to filter by")  # type: ignore[arg-type]
    infinite_mode: bool | None = Field(None, description="Filter by infinite mode status")
    search: str | None = Field(None, description="General search string")
    sort_by: str | None = Field(None, description="Sort field: 'date', 'score', or 'simulation_name'")
    sort_order: str | None = Field(None, description="Sort order: 'asc' or 'desc'")
    page: int | None = Field(0, description="Page number (0-indexed)")
    page_size: int | None = Field(20, description="Number of items per page")
    # Practice-only filters (ignored when practice=False)
    profile_ids: list[UUID] | None = Field(default_factory=list, description="Profile IDs to filter by (practice only)")  # type: ignore[arg-type]
    show_archived: bool | None = Field(False, description="Whether to include archived attempts")


class ChatSimulationCard(BaseModel):
    """Simulation card with analytical stats.

    SQL JOINs all metadata. Python computes: status, pass_pct, cohort_names_junction.
    Some fields are only populated based on mode:
    - completion_pct, passed_count, in_progress_count, not_started_count: instructional mode only
    - practice_simulation: practice mode only
    """

    view_mode: str = Field(..., description="View mode: 'member', 'instructional', or 'practice'")
    simulation_id: UUID = Field(..., description="UUID of the simulation")
    simulation_name: str | None = Field(None, description="Name of the simulation")
    simulation_description: str | None = Field(None, description="Description of the simulation")
    time_limit: int | None = Field(None, description="Time limit in seconds")
    num_sessions: int | None = Field(None, description="Number of attempt sessions")
    highest_score: int | None = Field(None, description="Highest score achieved")
    standard_groups: list[str] | None = Field(None, description="Standard group IDs as strings")
    color: str | None = Field(None, description="Persona display color")
    icon: str | None = Field(None, description="Persona icon identifier")
    has_passed: bool | None = Field(None, description="Whether the user has passed")
    # Computed by Python (business logic)
    status: str | None = Field(None, description="Status: 'passed', 'in-progress', or 'not-started'")
    pass_pct: int | None = Field(None, description="Pass percentage threshold")
    # Cohort info
    cohort_names_junction: str | None = Field(None, description="Formatted cohort names string")
    # Instructional mode only (home with elevated role)
    completion_pct: int | None = Field(None, description="Completion percentage (instructional only)")
    passed_count: int | None = Field(None, description="Number of students passed (instructional only)")
    in_progress_count: int | None = Field(None, description="Number of students in progress")
    not_started_count: int | None = Field(None, description="Number of students not started")
    # Practice mode only
    practice_simulation: bool | None = Field(None, description="Whether this is a practice simulation")


class ChatHistoryAttempt(BaseModel):
    """Attempt record for chat history.

    SQL JOINs all metadata. Python computes: score_status, show_view, show_continue, pass_pct.
    Some fields are only populated based on mode:
    - is_archived, practice_simulation, practice_scenario_id: practice mode only
    """

    attempt_id: UUID = Field(..., description="UUID of the attempt")
    date: str | None = Field(None, description="ISO timestamp of the attempt")
    profile_id: UUID | None = Field(None, description="UUID of the user profile")
    profile_name: str | None = Field(None, description="Display name of the user profile")
    simulation_id: UUID | None = Field(None, description="UUID of the simulation")
    simulation_name: str | None = Field(None, description="Name of the simulation")
    num_scenarios: int | None = Field(None, description="Total number of scenarios")
    num_scenarios_completed: int | None = Field(None, description="Number of scenarios completed")
    infinite_mode: bool | None = Field(None, description="Whether infinite mode is enabled")
    time_limit: int | None = Field(None, description="Time limit in seconds")
    persona_names_junction: list[str] | None = Field(None, description="Persona names for display")
    persona_colors_junction: list[str] | None = Field(None, description="Persona colors for display")
    scenario_ids: list[UUID] | None = Field(None, description="UUIDs of associated scenarios")
    scenario_titles: list[str] | None = Field(None, description="Titles of associated scenarios")
    department_ids: list[str] | None = Field(None, description="IDs of associated departments")
    cohort_names_junction: list[str] | None = Field(None, description="Cohort names for display")
    # Computed by Python (business logic)
    score: int | None = Field(None, description="Attempt score")
    score_status: str | None = Field(None, description="Score status: 'high', 'medium', or 'low'")
    pass_pct: int | None = Field(None, description="Pass percentage threshold")
    show_view: bool | None = Field(None, description="Whether to show the view action")
    show_continue: bool | None = Field(None, description="Whether to show the continue action")
    # Practice-only fields
    is_archived: bool | None = Field(None, description="Whether the attempt is archived")
    practice_simulation: bool | None = Field(None, description="Whether this is a practice simulation")
    practice_scenario_id: UUID | None = Field(None, description="UUID of the practice scenario")


class GetChatListResponse(BaseModel):
    """Client-facing API response for chat list (analytical).

    Combines simulation cards AND paginated attempt history in one response.
    """

    actor_name: str | None = Field(None, description="Display name of the current actor")
    mode: str | None = Field(None, description="View mode: 'member', 'instructional', or 'practice'")
    has_data: bool | None = Field(None, description="Whether any data exists")
    # Simulation cards (overview)
    items: list[ChatSimulationCard] | None = Field(None, description="Simulation card items")
    standard_groups: list[StandardGroupMapping] | None = Field(None, description="Standard group mappings")
    standards: list[StandardMapping] | None = Field(None, description="Standard mappings")
    # Attempt history (paginated)
    data: list[ChatHistoryAttempt] | None = Field(None, description="Attempt history items")
    total_count: int | None = Field(None, description="Total number of matching results")
    page: int | None = Field(None, description="Current page number")
    page_size: int | None = Field(None, description="Number of items per page")
    total_pages: int | None = Field(None, description="Total number of pages")
    # Filter options
    simulation_options: list[FilterOption] | None = Field(None, description="Simulation filter options")
    scenario_options: list[FilterOption] | None = Field(None, description="Scenario filter options")
    profile_options: list[FilterOption] | None = Field(None, description="Profile filter options (practice only)")


# =============================================================================
# GET endpoint types (OPERATIONAL) - Simulations user can take
# =============================================================================


class ChatSimulationOperational(BaseModel):
    """Simulation data for starting a chat session.

    Contains data needed to start a simulation AND card display stats.
    Now serves as the unified type for home/practice simulation cards.
    """

    simulation_id: UUID = Field(..., description="UUID of the simulation")
    simulation_name: str | None = Field(None, description="Name of the simulation")
    simulation_description: str | None = Field(None, description="Description of the simulation")
    time_limit: int | None = Field(None, description="Time limit in seconds")
    chat_entry_id: UUID | None = Field(None, description="UUID of the chat entry")
    home_id: UUID | None = Field(None, description="UUID of the home entry")
    practice_id: UUID | None = Field(None, description="UUID of the practice entry")
    scenario_ids: list[UUID] | None = Field(None, description="Ordered list of scenario IDs")
    cohort_ids: list[UUID] | None = Field(None, description="Cohort IDs this simulation belongs to")
    # Display metadata
    color: str | None = Field(None, description="Persona display color")
    icon: str | None = Field(None, description="Persona icon identifier")
    # Card stats from mv_profile_facts
    view_mode: str | None = Field(None, description="View mode: 'member', 'instructional', or 'practice'")
    num_sessions: int | None = Field(None, description="Number of attempt sessions")
    highest_score: int | None = Field(None, description="Highest score percentage rounded")
    has_passed: bool | None = Field(None, description="Whether the user has passed")
    # Computed by Python (business logic)
    status: str | None = Field(None, description="Status: 'passed', 'in-progress', or 'not-started'")
    pass_pct: int | None = Field(None, description="Pass percentage threshold")
    # Cohort info
    cohort_names_junction: str | None = Field(None, description="Formatted cohort names string")
    # Standard groups for rubric display
    standard_groups: list[str] | None = Field(None, description="Standard group IDs as strings")
    # Practice mode flag
    practice_simulation: bool | None = Field(None, description="Whether this is a practice simulation")
    # Instructional mode only (home with elevated role)
    completion_pct: int | None = Field(None, description="Completion percentage (instructional only)")
    passed_count: int | None = Field(None, description="Number of students passed (instructional only)")
    in_progress_count: int | None = Field(None, description="Number of students in progress")
    not_started_count: int | None = Field(None, description="Number of students not started")


# =============================================================================
# BUNDLE endpoint types (customize/start flow) — canonical flat-array pattern
# =============================================================================


class SectionFilter(BaseModel):
    """Per-section filter options for chat GET requests."""

    search: str | None = Field(None, description="Filter options by search text")
    limit: int | None = Field(None, description="Max options to return")
    selected: bool | None = Field(None, description="Only return selected items")
    suggested: bool | None = Field(None, description="Only return suggested items")
    include: bool | None = Field(None, description="Include this section in the response")
    parameter_ids: list[str] | None = Field(
        None,
        description="Parameter IDs to filter parameter_fields by",
    )


class ChatNameResource(BaseModel):
    id: UUID | None = None
    name: str | None = None
    generated: bool | None = None
    suggested: bool = False
    selected: bool = False
    pending: bool = False


class ChatDescriptionResource(BaseModel):
    id: UUID | None = None
    description: str | None = None
    generated: bool | None = None
    suggested: bool = False
    selected: bool = False
    pending: bool = False


class ChatFlagResource(BaseModel):
    id: UUID | None = None
    name: str | None = None
    description: str | None = None
    type: str | None = None
    icon: str | None = None
    value: bool | None = None
    generated: bool | None = None
    suggested: bool = False
    selected: bool = False
    pending: bool = False


class ChatDepartmentResource(BaseModel):
    department_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    generated: bool | None = None
    suggested: bool = False
    selected: bool = False
    pending: bool = False


class ChatPersonaResource(BaseModel):
    persona_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    generated: bool | None = None
    suggested: bool = False
    selected: bool = False
    pending: bool = False


class ChatDocumentResource(BaseModel):
    document_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    file_id: UUID | None = None
    text_id: UUID | None = None
    image_ids: list[UUID] | None = None
    template: bool | None = None
    parameter_field_ids: list[UUID] | None = None
    generated: bool | None = None
    suggested: bool = False
    selected: bool = False
    pending: bool = False


class ChatParameterFieldResource(BaseModel):
    id: UUID | None = None
    field_id: UUID | None = None
    parameter_id: UUID | None = None
    name: str | None = None
    parameter_name: str | None = None
    generated: bool | None = None
    suggested: bool = False
    selected: bool = False
    pending: bool = False


class ChatScenarioResource(BaseModel):
    scenario_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    generated: bool | None = None
    suggested: bool = False
    selected: bool = False
    pending: bool = False


class ChatFieldResource(BaseModel):
    field_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    value: str | None = None
    conditional_parameter_ids: list[UUID] | None = None
    generated: bool | None = None
    suggested: bool = False
    selected: bool = False
    pending: bool = False


class ChatQuestionResource(BaseModel):
    question_id: UUID | None = None
    question_text: str | None = None
    allow_multiple: bool | None = None
    time: int | None = None
    generated: bool | None = None
    suggested: bool = False
    selected: bool = False
    pending: bool = False


class ChatOptionResource(BaseModel):
    option_id: UUID | None = None
    option_text: str | None = None
    question_id: UUID | None = None
    is_correct: bool | None = None
    generated: bool | None = None
    suggested: bool = False
    selected: bool = False
    pending: bool = False


class ChatVideoResource(BaseModel):
    video_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    length_seconds: int | None = None
    generated: bool | None = None
    suggested: bool = False
    selected: bool = False
    pending: bool = False


class ChatImageResource(BaseModel):
    image_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    generated: bool | None = None
    suggested: bool = False
    selected: bool = False
    pending: bool = False


class ChatProblemStatementResource(BaseModel):
    problem_statement_id: UUID | None = None
    name: str | None = None
    problem_statement: str | None = None
    generated: bool | None = None
    suggested: bool = False
    selected: bool = False
    pending: bool = False


class ChatObjectiveResource(BaseModel):
    id: UUID | None = None
    objective: str | None = None
    generated: bool | None = None
    suggested: bool = False
    selected: bool = False
    pending: bool = False


class GetChatRequest(BaseModel):
    """Canonical chat customization request."""

    id: UUID | None = Field(None, description="Chat entry ID")
    chat_entry_id: UUID | None = Field(None, description="Legacy alias for the chat entry ID")
    attempt_id: UUID | None = Field(None, description="Attempt ID")
    draft_id: UUID | None = Field(None, description="Draft ID")
    snapshot_key: str | None = Field(None, description="Cache snapshot key for consistent reads")
    names: SectionFilter | None = None
    descriptions: SectionFilter | None = None
    flags: SectionFilter | None = None
    departments: SectionFilter | None = None
    personas: SectionFilter | None = None
    documents: SectionFilter | None = None
    parameter_fields: SectionFilter | None = None
    scenarios: SectionFilter | None = None
    fields: SectionFilter | None = None
    questions: SectionFilter | None = None
    options: SectionFilter | None = None
    videos: SectionFilter | None = None
    images: SectionFilter | None = None
    problem_statements: SectionFilter | None = None
    objectives: SectionFilter | None = None


class GetChatResponse(BaseModel):
    """Canonical chat bundle response."""

    actor_name: str | None = Field(None, description="Display name of the authenticated user")
    chat_exists: bool | None = Field(None, description="Whether the chat template exists")
    can_edit: bool | None = Field(None, description="Whether the current user can edit this draft")
    disabled_reason: str | None = Field(None, description="Human-readable reason if editing is disabled")
    group_id: UUID | None = Field(None, description="Group ID for generation and draft correlation")
    show_ai_generate: bool | None = Field(None, description="Whether AI generation is available")
    profile_has_access: bool | None = Field(True, description="Compatibility flag for current chat pages")
    simulation_name: str | None = Field(None, description="Optional simulation name for UI display")
    chat_entry_id: UUID | None = Field(None, description="Chat entry ID")
    attempt_id: UUID | None = Field(None, description="Attempt ID")

    names: list[ChatNameResource] | None = None
    descriptions: list[ChatDescriptionResource] | None = None
    flags: list[ChatFlagResource] | None = None
    departments: list[ChatDepartmentResource] | None = None
    personas: list[ChatPersonaResource] | None = None
    documents: list[ChatDocumentResource] | None = None
    parameter_fields: list[ChatParameterFieldResource] | None = None
    scenarios: list[ChatScenarioResource] | None = None
    fields: list[ChatFieldResource] | None = None
    questions: list[ChatQuestionResource] | None = None
    options: list[ChatOptionResource] | None = None
    videos: list[ChatVideoResource] | None = None
    images: list[ChatImageResource] | None = None
    problem_statements: list[ChatProblemStatementResource] | None = None
    objectives: list[ChatObjectiveResource] | None = None

    # Compatibility fields for attempt generation consumers.
    name_ids: list[UUID] | None = None
    description_ids: list[UUID] | None = None
    flag_ids: list[UUID] | None = None
    department_ids: list[UUID] | None = None
    persona_ids: list[UUID] | None = None
    document_ids: list[UUID] | None = None
    parameter_field_ids: list[UUID] | None = None
    scenario_ids: list[UUID] | None = None
    field_ids: list[UUID] | None = None
    question_ids: list[UUID] | None = None
    option_ids: list[UUID] | None = None
    video_ids: list[UUID] | None = None
    image_ids: list[UUID] | None = None
    problem_statement_ids: list[UUID] | None = None
    objective_ids: list[UUID] | None = None


# =============================================================================
# Bundle Draft endpoint types (composable infra)
# =============================================================================


# =============================================================================
# Draft value types (for creatable resources)
# =============================================================================


class DraftImageValue(BaseModel):
    """Value for creating an image via the draft endpoint."""

    name: str = Field(..., description="Name of the image")
    description: str = Field(..., description="Description of the image")
    upload_id: UUID | None = Field(
        None, description="UUID of the uploaded file"
    )


class DraftVideoValue(BaseModel):
    """Value for creating a video via the draft endpoint."""

    name: str = Field(..., description="Name of the video")
    description: str = Field(..., description="Description of the video")
    upload_id: UUID | None = Field(
        None, description="UUID of the uploaded file"
    )


class DraftQuestionValue(BaseModel):
    """Value for creating a question via the draft endpoint."""

    question_text: str = Field(..., description="Text of the question")
    time: int = Field(30, description="Video timestamp in seconds")
    allow_multiple: bool = Field(False, description="Whether multiple answers are allowed")


class DraftOptionValue(BaseModel):
    """Value for creating an option via the draft endpoint."""

    option_text: str = Field(..., description="Display text for the option")
    question_id: UUID | None = Field(None, description="UUID of the parent question")


class PatchChatDraftApiRequest(ScopedItem):
    """Canonical chat draft request."""

    draft_id: UUID | None = Field(None, description="Existing draft ID to update")
    input_draft_id: UUID | None = Field(None, description="Legacy alias for draft_id")

    # Single-select creatables
    name: str | None = None
    name_id: UUID | None = None
    description: str | None = None
    description_id: UUID | None = None
    problem_statement: str | None = None
    problem_statement_id: UUID | None = None

    # Multi-select creatables
    objectives: list[str] | None = None
    objective_ids: list[UUID] | None = None
    images: list[DraftImageValue] | None = None
    image_ids: list[UUID] | None = None
    videos: list[DraftVideoValue] | None = None
    video_ids: list[UUID] | None = None
    questions: list[DraftQuestionValue] | None = None
    question_ids: list[UUID] | None = None
    options: list[DraftOptionValue] | None = None
    option_ids: list[UUID] | None = None

    # Match/select-only
    department_ids: list[UUID] | None = None
    document_ids: list[UUID] | None = None
    field_ids: list[UUID] | None = None
    flag_ids: list[UUID] | None = None
    parameter_field_ids: list[UUID] | None = None
    parameter_ids: list[UUID] | None = None
    persona_ids: list[UUID] | None = None
    scenario_ids: list[UUID] | None = None

    pending_ids: list[UUID] | None = Field(None, description="Resource IDs to keep pending/inactive on the draft")
    idempotency_key: UUID | None = Field(None, description="Ack key for generation/correlation flows")
    accept: bool = Field(True, description="Accept or reject pending state")

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
        "department_ids": "departments",
        "document_ids": "documents",
        "field_ids": "fields",
        "flag_ids": "flags",
        "parameter_field_ids": "parameter_fields",
        "parameter_ids": "parameters",
        "persona_ids": "personas",
        "scenario_ids": "scenarios",
    }


class SaveChatFieldError(BaseModel):
    """Per-field error from draft value resolution."""

    field: str = Field(..., description="Name of the field with the error")
    message: str = Field(..., description="Error message for the field")


# =============================================================================
# Chat Draft Form State (for form_state sync)
# =============================================================================


class ChatDraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_id: UUID | None = None
    name: str | None = None
    description_id: UUID | None = None
    description: str | None = None
    problem_statement_id: UUID | None = None
    problem_statement: str | None = None
    department_ids: list[UUID] = Field(default_factory=list)
    document_ids: list[UUID] = Field(default_factory=list)
    field_ids: list[UUID] = Field(default_factory=list)
    flag_ids: list[UUID] = Field(default_factory=list)
    image_ids: list[UUID] = Field(default_factory=list)
    objective_ids: list[UUID] = Field(default_factory=list)
    option_ids: list[UUID] = Field(default_factory=list)
    parameter_field_ids: list[UUID] = Field(default_factory=list)
    parameter_ids: list[UUID] = Field(default_factory=list)
    persona_ids: list[UUID] = Field(default_factory=list)
    question_ids: list[UUID] = Field(default_factory=list)
    scenario_ids: list[UUID] = Field(default_factory=list)
    video_ids: list[UUID] = Field(default_factory=list)
    pending_ids: list[UUID] = Field(default_factory=list)


class PatchChatDraftApiResponse(BaseModel):
    """Response model for new-style chat draft endpoint."""

    success: bool = Field(..., description="Whether the draft save succeeded")
    draft_id: UUID = Field(..., description="UUID of the saved draft")
    idempotency_key: UUID | None = Field(None, description="Idempotency key for client correlation")
    message: str = Field(..., description="Response message")
    form_state: ChatDraftFormState | None = Field(None, description="Updated form state after save")


# =============================================================================
# Chat START websocket types (for chat start socket handler)
# =============================================================================


class ChatStartWebsocketEntries(BaseModel):
    """Thin websocket views payload for chat start."""

    chat_entry_id: UUID = Field(..., description="UUID of the chat entry")
    department_id: UUID = Field(..., description="UUID of the department")


class ChatStartWebsocketResources(BaseModel):
    """Chat resources for start websocket handlers."""

    simulation_id: UUID | None = Field(None, description="UUID of the simulation")
    scenario_id: UUID | None = Field(None, description="UUID of the scenario")
    problem_statement: str | None = Field(None, description="Problem statement text")
    objectives: dict | list | None = Field(None, description="Objectives data")
    persona: dict | None = Field(None, description="Persona configuration data")
    video_ids: list[UUID] | None = Field(None, description="UUIDs of associated videos")
    image_ids: list[UUID] | None = Field(None, description="UUIDs of associated images")
    has_problem_statement: bool = Field(False, description="Whether a problem statement exists")
    has_persona: bool = Field(False, description="Whether a persona is configured")
    agent_id: UUID | None = Field(None, description="UUID of the AI agent")
    agent_exists: bool = Field(False, description="Whether the agent exists")
    agent_name: str | None = Field(None, description="Name of the AI agent")
    agent_is_active: bool = Field(False, description="Whether the agent is active")
    model_id: UUID | None = Field(None, description="UUID of the AI model")
    model_name: str | None = Field(None, description="Name of the AI model")
    provider_id: UUID | None = Field(None, description="UUID of the AI provider")
    provider_name: str | None = Field(None, description="Name of the AI provider")
    has_api_key: bool = Field(False, description="Whether an API key is configured")
    request_limit: int | None = Field(None, description="Rate limit from role")
    runs_today: int = Field(0, description="Number of runs used today")
    simulation_exists: bool = Field(False, description="Whether the simulation exists")
    simulation_is_active: bool = Field(False, description="Whether the simulation is active")
    profile_has_access: bool = Field(False, description="Whether the profile has access")
    valid_entry_types: list[str] = Field(default_factory=list, description="Valid entry types for the chat")


class GetChatStartWebsocketResponse(InternalResponseBase):
    """Websocket-facing chat start response."""

    entries: ChatStartWebsocketEntries = Field(..., description="Websocket entry data")
    resources: ChatStartWebsocketResources = Field(..., description="Websocket resource data")


# =============================================================================
# Backwards compatibility aliases (deprecated)
# =============================================================================

# These will be removed in a future version
GetChatHistoryRequest = GetChatListRequest
GetChatHistoryResponse = GetChatListResponse
GetChatOverviewRequest = GetChatListRequest
GetChatOverviewResponse = GetChatListResponse
