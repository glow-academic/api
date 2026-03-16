"""Custom types for unified chat endpoints.

These types define the client-facing API contract for both home and practice
modes via a single `practice: bool` parameter. Internal parameters (mode,
accessible_cohort_ids) are NOT included here - they are injected by Python.

Architecture:
- list.py (ANALYTICAL): Simulation cards + attempt history + filter options
- get.py (OPERATIONAL): Simulations user can take + scenario_ids + rubric data
- bundle.py (BUNDLE): Section-first customization before starting chat
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.v5_types import InternalResponseBase
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
# BUNDLE endpoint types (customize/start flow) — Section-first pattern
# =============================================================================


class GetChatRequest(BaseModel):
    """Client API request for one chat bundle customization payload."""

    chat_entry_id: UUID = Field(..., description="UUID of the chat entry")
    attempt_id: UUID | None = Field(None, description="UUID of the attempt")
    draft_id: UUID | None = Field(None, description="UUID of the draft")
    # Search filters (analogous to scenario)
    description_search: str | None = Field(None, description="Search filter for descriptions")
    persona_search: str | None = Field(None, description="Search filter for personas")
    document_search: str | None = Field(None, description="Search filter for documents")
    problem_statement_search: str | None = Field(None, description="Search filter for problem statements")
    image_search: str | None = Field(None, description="Search filter for images")
    video_search: str | None = Field(None, description="Search filter for videos")
    question_search: str | None = Field(None, description="Search filter for questions")
    option_search: str | None = Field(None, description="Search filter for options")
    # Show-selected toggles
    persona_show_selected: bool | None = Field(None, description="Whether to show only selected personas")
    document_show_selected: bool | None = Field(None, description="Whether to show only selected documents")


# --- Section types (one per resource) ---


class BaseChatSection(BaseModel):
    """Common metadata fields for all chat bundle resource sections."""

    show: bool = Field(False, description="Whether to show this section")
    required: bool = Field(False, description="Whether this section is required")
    suggestions: list[UUID] | None = Field(None, description="Suggested resource IDs")
    show_ai_generate: bool = Field(False, description="Whether to show AI generate option")


class ChatDepartmentSection(BaseChatSection):
    current: list[Any] | None = Field(None, description="Currently selected departments")
    resources: list[Any] | None = Field(None, description="Available department resources")


class ChatPersonaSection(BaseChatSection):
    current: list[Any] | None = Field(None, description="Currently selected personas")
    resources: list[Any] | None = Field(None, description="Available persona resources")


class ChatDocumentSection(BaseChatSection):
    current: list[Any] | None = Field(None, description="Currently selected documents")
    resources: list[Any] | None = Field(None, description="Available document resources")


class ChatParameterFieldSection(BaseChatSection):
    current: list[Any] | None = Field(None, description="Currently selected parameter fields")
    resources: list[Any] | None = Field(None, description="Available parameter field resources")


class ChatScenarioSection(BaseChatSection):
    current: list[Any] | None = Field(None, description="Currently selected scenarios")
    resources: list[Any] | None = Field(None, description="Available scenario resources")


class ChatFieldSection(BaseChatSection):
    current: list[Any] | None = Field(None, description="Currently selected fields")
    resources: list[Any] | None = Field(None, description="Available field resources")


class ChatQuestionSection(BaseChatSection):
    current: list[Any] | None = Field(None, description="Currently selected questions")
    resources: list[Any] | None = Field(None, description="Available question resources")


class ChatOptionSection(BaseChatSection):
    current: list[Any] | None = Field(None, description="Currently selected options")
    resources: list[Any] | None = Field(None, description="Available option resources")


class ChatVideoSection(BaseChatSection):
    current: list[Any] | None = Field(None, description="Currently selected videos")
    resources: list[Any] | None = Field(None, description="Available video resources")


class ChatImageSection(BaseChatSection):
    current: list[Any] | None = Field(None, description="Currently selected images")
    resources: list[Any] | None = Field(None, description="Available image resources")


class ChatProblemStatementSection(BaseChatSection):
    current: list[Any] | None = Field(None, description="Currently selected problem statements")
    resources: list[Any] | None = Field(None, description="Available problem statement resources")


class ChatObjectiveSection(BaseChatSection):
    current: list[Any] | None = Field(None, description="Currently selected objectives")
    resources: list[Any] | None = Field(None, description="Available objective resources")


class ChatNameSection(BaseChatSection):
    current: list[Any] | None = Field(None, description="Currently selected names")
    resources: list[Any] | None = Field(None, description="Available name resources")


class ChatDescriptionSection(BaseChatSection):
    current: list[Any] | None = Field(None, description="Currently selected descriptions")
    resources: list[Any] | None = Field(None, description="Available description resources")


class ChatFlagSection(BaseChatSection):
    current: list[Any] | None = Field(None, description="Currently selected flags")
    resources: list[Any] | None = Field(None, description="Available flag resources")


# --- Scenario flags type ---


class ChatScenarioFlags(BaseModel):
    """Scenario-level flags that control section visibility."""

    video_enabled: bool = Field(False, description="Whether video section is enabled")
    problem_statement_enabled: bool = Field(False, description="Whether problem statement is enabled")
    objectives_enabled: bool = Field(False, description="Whether objectives section is enabled")
    images_enabled: bool = Field(False, description="Whether images section is enabled")
    questions_enabled: bool = Field(False, description="Whether questions section is enabled")


# --- GET response (section-first) ---


class GetChatResponse(BaseModel):
    """Client-facing chat bundle response — section-first pattern."""

    chat_entry_id: UUID = Field(..., description="UUID of the chat entry")
    attempt_id: UUID | None = Field(None, description="UUID of the attempt")
    group_id: UUID = Field(..., description="UUID of the group")
    draft_version: int | None = Field(None, description="Current draft version number")

    # 15 section-first resources
    names: ChatNameSection | None = Field(None, description="Name section data")
    descriptions: ChatDescriptionSection | None = Field(None, description="Description section data")
    flags: ChatFlagSection | None = Field(None, description="Flag section data")
    departments: ChatDepartmentSection | None = Field(None, description="Department section data")
    personas: ChatPersonaSection | None = Field(None, description="Persona section data")
    documents: ChatDocumentSection | None = Field(None, description="Document section data")
    parameter_fields: ChatParameterFieldSection | None = Field(None, description="Parameter field section data")
    scenarios: ChatScenarioSection | None = Field(None, description="Scenario section data")
    fields: ChatFieldSection | None = Field(None, description="Field section data")
    questions: ChatQuestionSection | None = Field(None, description="Question section data")
    options: ChatOptionSection | None = Field(None, description="Option section data")
    videos: ChatVideoSection | None = Field(None, description="Video section data")
    images: ChatImageSection | None = Field(None, description="Image section data")
    problem_statements: ChatProblemStatementSection | None = Field(None, description="Problem statement section data")
    objectives: ChatObjectiveSection | None = Field(None, description="Objective section data")


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


class PatchChatDraftApiRequest(BaseModel):
    """Request model for new-style chat draft endpoint.

    Single-select creatables: name, description, problem_statement
      → value creates resource, ID replaces value (mutually exclusive).

    Multi-select creatables: objectives, images, videos, questions, options
      → values create resources, created IDs are merged with existing IDs.

    Client always sends full state (append-only — each write is a new version snapshot).
    """

    input_draft_id: UUID | None = Field(None, description="UUID of the input draft")
    expected_version: int = Field(0, description="Expected version for optimistic locking")

    # Single-select creatables — provide value OR ID
    name: str | None = Field(None, description="Name value to create")
    description: str | None = Field(None, description="Description value to create")
    problem_statement: str | None = Field(None, description="Problem statement value to create")

    # Multi-select creatables — values create resources, merged with IDs
    objectives: list[str] | None = Field(None, description="Objective texts to create")
    images: list[DraftImageValue] | None = Field(None, description="Image values to create")
    videos: list[DraftVideoValue] | None = Field(None, description="Video values to create")
    questions: list[DraftQuestionValue] | None = Field(None, description="Question values to create")
    options: list[DraftOptionValue] | None = Field(None, description="Option values to create")

    # All ID-only
    name_ids: list[UUID] | None = Field(None, description="Selected name resource IDs")
    description_ids: list[UUID] | None = Field(None, description="Selected description resource IDs")
    document_ids: list[UUID] | None = Field(None, description="Selected document resource IDs")
    field_ids: list[UUID] | None = Field(None, description="Selected field resource IDs")
    flag_ids: list[UUID] | None = Field(None, description="Selected flag resource IDs")
    image_ids: list[UUID] | None = Field(None, description="Selected image resource IDs")
    objective_ids: list[UUID] | None = Field(None, description="Selected objective resource IDs")
    option_ids: list[UUID] | None = Field(None, description="Selected option resource IDs")
    parameter_field_ids: list[UUID] | None = Field(None, description="Selected parameter field resource IDs")
    parameter_ids: list[UUID] | None = Field(None, description="Selected parameter resource IDs")
    persona_ids: list[UUID] | None = Field(None, description="Selected persona resource IDs")
    problem_statement_ids: list[UUID] | None = Field(None, description="Selected problem statement resource IDs")
    question_ids: list[UUID] | None = Field(None, description="Selected question resource IDs")
    scenario_ids: list[UUID] | None = Field(None, description="Selected scenario resource IDs")
    video_ids: list[UUID] | None = Field(None, description="Selected video resource IDs")
    department_ids: list[UUID] | None = Field(None, description="Selected department resource IDs")


class SaveChatFieldError(BaseModel):
    """Per-field error from draft value resolution."""

    field: str = Field(..., description="Name of the field with the error")
    message: str = Field(..., description="Error message for the field")


# =============================================================================
# Chat Draft Form State (for form_state sync)
# =============================================================================


class ChatDraftFormState(BaseModel):
    """Server-authoritative form state returned after draft save."""

    name_ids: list[UUID] = Field(default_factory=list, description="Selected name resource IDs")
    description_ids: list[UUID] = Field(default_factory=list, description="Selected description resource IDs")
    flag_ids: list[UUID] = Field(default_factory=list, description="Selected flag resource IDs")
    department_ids: list[UUID] = Field(default_factory=list, description="Selected department resource IDs")
    persona_ids: list[UUID] = Field(default_factory=list, description="Selected persona resource IDs")
    document_ids: list[UUID] = Field(default_factory=list, description="Selected document resource IDs")
    parameter_field_ids: list[UUID] = Field(default_factory=list, description="Selected parameter field resource IDs")
    parameter_ids: list[UUID] = Field(default_factory=list, description="Selected parameter resource IDs")
    scenario_ids: list[UUID] = Field(default_factory=list, description="Selected scenario resource IDs")
    field_ids: list[UUID] = Field(default_factory=list, description="Selected field resource IDs")
    question_ids: list[UUID] = Field(default_factory=list, description="Selected question resource IDs")
    option_ids: list[UUID] = Field(default_factory=list, description="Selected option resource IDs")
    video_ids: list[UUID] = Field(default_factory=list, description="Selected video resource IDs")
    image_ids: list[UUID] = Field(default_factory=list, description="Selected image resource IDs")
    problem_statement_ids: list[UUID] = Field(default_factory=list, description="Selected problem statement resource IDs")
    objective_ids: list[UUID] = Field(default_factory=list, description="Selected objective resource IDs")


class PatchChatDraftApiResponse(BaseModel):
    """Response model for new-style chat draft endpoint."""

    success: bool = Field(..., description="Whether the draft save succeeded")
    draft_id: UUID = Field(..., description="UUID of the saved draft")
    new_version: int = Field(..., description="New version number after save")
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
    requests_per_day: int | None = Field(None, description="Rate limit for requests per day")
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
