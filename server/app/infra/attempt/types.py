"""Custom types for unified attempt detail endpoint.

These types define the client-facing API contract for attempt detail.
The practice flag is determined server-side from the attempt data itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.v5_types import ListFilterSection
from app.tools.entries.attempt.types import GetAttemptResponse
from app.tools.entries.attempt_chat.types import GetAttemptChatResponse
from app.tools.entries.attempt_message.types import GetAttemptMessageResponse
from app.tools.entries.runs.search import GetRunListViewResponse

# =============================================================================
# Attempt detail endpoint types (client-facing)
# =============================================================================

# -----------------------------------------------------------------------------
# Video/Quiz types
# -----------------------------------------------------------------------------


class VideoQuestionOption(BaseModel):
    """Option for a video question."""

    id: UUID = Field(..., description="Unique identifier of the option")
    option_text: str | None = Field(None, description="Display text for the option")
    type: str | None = Field(None, description="Type of the option")
    is_correct: bool | None = Field(None, description="Whether this option is correct")


class VideoQuestion(BaseModel):
    """Question for a video."""

    id: UUID = Field(..., description="Unique identifier of the question")
    question_text: str | None = Field(None, description="Text of the question")
    type: str | None = Field(None, description="Type of the question")
    allow_multiple: bool | None = Field(None, description="Whether multiple answers are allowed")
    times: list[int] | None = Field(None, description="Video timestamps to show the question")
    options: list[VideoQuestionOption] | None = Field(None, description="Available answer options")


class VideoData(BaseModel):
    """Video information for a chat (legacy - use VideoEntry instead)."""

    id: UUID | None = Field(None, description="UUID of the video")
    title: str | None = Field(None, description="Title of the video")
    upload_id: UUID | None = Field(None, description="UUID of the uploaded file")
    questions: list[VideoQuestion] | None = Field(None, description="Questions associated with the video")
    show_image: bool | None = Field(None, description="Whether to show the video thumbnail")


# -----------------------------------------------------------------------------
# Unified asset entry types (id, upload_id, name, description)
# -----------------------------------------------------------------------------


class ImageEntry(BaseModel):
    """Image entry with resource metadata."""

    image_id: UUID | None = Field(None, description="UUID of the image")
    upload_id: UUID | None = Field(None, description="UUID of the uploaded file")
    name: str | None = Field(None, description="Name of the image")
    description: str | None = Field(None, description="Description of the image")


class VideoEntry(BaseModel):
    """Video entry with resource metadata."""

    video_id: UUID | None = Field(None, description="UUID of the video")
    upload_id: UUID | None = Field(None, description="UUID of the uploaded file")
    name: str | None = Field(None, description="Name of the video")
    description: str | None = Field(None, description="Description of the video")


class DocumentEntry(BaseModel):
    """Document entry with resource metadata."""

    document_id: UUID | None = Field(None, description="UUID of the document")
    upload_id: UUID | None = Field(None, description="UUID of the uploaded file")
    name: str | None = Field(None, description="Name of the document")
    description: str | None = Field(None, description="Description of the document")
    template: bool | None = Field(None, description="Whether this document is a template")


class AnalysisEntry(BaseModel):
    """Analysis entry for chat-level analysis content."""

    content: str | None = Field(None, description="Analysis content text")


class ObjectiveEntry(BaseModel):
    """Objective entry with resource metadata."""

    objective_id: UUID | None = Field(None, description="UUID of the objective")
    objective: str | None = Field(None, description="Objective text")


class ProblemStatementEntry(BaseModel):
    """Problem statement entry with resource metadata."""

    problem_statement_id: UUID | None = Field(None, description="UUID of the problem statement")
    problem_statement: str | None = Field(None, description="Problem statement text")


class OptionEntry(BaseModel):
    """Option entry nested under a question."""

    option_id: UUID | None = Field(None, description="UUID of the option")
    question_id: UUID | None = Field(None, description="UUID of the parent question")
    option_text: str | None = Field(None, description="Display text for the option")
    is_correct: bool | None = Field(None, description="Whether this option is correct")


class QuestionEntry(BaseModel):
    """Question entry with nested options and times.

    Options are nested directly under the question.
    Times indicates video timestamps (seconds) when to show this question.
    """

    question_id: UUID | None = Field(None, description="UUID of the question")
    question_text: str | None = Field(None, description="Text of the question")
    allow_multiple: bool | None = Field(None, description="Whether multiple answers are allowed")
    times: list[int] | None = Field(None, description="Video timestamps when to show")
    options: list[OptionEntry] | None = Field(None, description="Nested options for the question")


class QuizResponse(BaseModel):
    """Quiz response entry."""

    question_id: UUID | None = Field(None, description="UUID of the answered question")
    option_id: UUID | None = Field(None, description="UUID of the selected option")
    completed: bool | None = Field(None, description="Whether the response is complete")
    created_at: datetime | None = Field(None, description="Timestamp when response was created")


class QuizData(BaseModel):
    """Quiz information for a chat."""

    id: UUID | None = Field(None, description="UUID of the quiz")
    completed: bool | None = Field(None, description="Whether the quiz is completed")
    responses: list[QuizResponse] | None = Field(None, description="Quiz responses submitted")


# -----------------------------------------------------------------------------
# Grading state types (Record format - server sends what client needs)
# -----------------------------------------------------------------------------


class GradingStateData(BaseModel):
    """Grading state for a chat in Record format.

    All fields are Records keyed by standard_id strings.
    This is the exact format the client needs - no transformation required.
    """

    # standard_id -> achieved (boolean)
    achieved_standards: dict[str, bool] | None = Field(None, description="Map of standard_id to achieved status")
    # standard_id -> passed (boolean)
    passed_standards: dict[str, bool] | None = Field(None, description="Map of standard_id to passed status")
    # standard_id -> feedback (string)
    feedback_by_standard_id: dict[str, str] | None = Field(None, description="Map of standard_id to feedback text")


# -----------------------------------------------------------------------------
# Dynamic rubric types
# -----------------------------------------------------------------------------


class SkillScore(BaseModel):
    """Skill score entry."""

    skill_name: str | None = Field(None, description="Name of the skill")
    score: float | None = Field(None, description="Score for the skill")


class SkillFeedback(BaseModel):
    """Skill feedback entry."""

    skill_name: str | None = Field(None, description="Name of the skill")
    feedback: str | None = Field(None, description="Feedback text for the skill")


class DynamicRubricData(BaseModel):
    """Dynamic rubric information for a chat."""

    chat_id: UUID | None = Field(None, description="UUID of the chat")
    score: float | None = Field(None, description="Overall rubric score")
    passed: bool | None = Field(None, description="Whether the rubric was passed")
    time_taken: float | None = Field(None, description="Time taken in seconds")
    skill_scores: list[SkillScore] | None = Field(None, description="Scores per skill")
    skill_feedbacks: list[SkillFeedback] | None = Field(None, description="Feedback per skill")
    total_possible_points: float | None = Field(None, description="Maximum possible points")


# -----------------------------------------------------------------------------
# Rubric structure types (Record format - server sends what client needs)
# -----------------------------------------------------------------------------


class StandardGroupMeta(BaseModel):
    """Standard group metadata for rubric display."""

    name: str | None = Field(None, description="Name of the standard group")
    description: str | None = Field(None, description="Description of the standard group")
    points: float | None = Field(None, description="Total points for the group")
    pass_points: float | None = Field(None, description="Points required to pass")


class StandardMeta(BaseModel):
    """Standard metadata for rubric display."""

    name: str | None = Field(None, description="Name of the standard")
    description: str | None = Field(None, description="Description of the standard")
    points: float | None = Field(None, description="Points for the standard")


class RubricStructureData(BaseModel):
    """Rubric structure data in Record format.

    All fields are Records keyed by standard_group_id or standard_id strings.
    This is the exact format the client needs - no transformation required.
    """

    # standard_group_id -> list of standard_id strings
    standard_groups: dict[str, list[str]] | None = Field(None, description="Map of group_id to standard_id lists")
    # standard_group_id -> metadata
    standard_groups_mapping: dict[str, StandardGroupMeta] | None = Field(None, description="Map of group_id to group metadata")
    # standard_id -> metadata
    standards_mapping: dict[str, StandardMeta] | None = Field(None, description="Map of standard_id to standard metadata")


# -----------------------------------------------------------------------------
# Attempt grading request types
# -----------------------------------------------------------------------------


class AttemptGradeFeedbackEntry(BaseModel):
    """Agent-provided feedback for an attempt grade."""

    feedback: str = Field(..., description="Feedback text from the agent")
    total: int | None = Field(None, description="Total score for this feedback")


class AttemptGradeStrengthEntry(BaseModel):
    """Agent-provided strength for an attempt grade."""

    name: str = Field(..., description="Name of the strength")
    description: str = Field(..., description="Description of the strength")
    message_id: UUID | None = Field(None, description="UUID of the associated message")


class AttemptGradeImprovementEntry(BaseModel):
    """Agent-provided improvement for an attempt grade."""

    name: str = Field(..., description="Name of the improvement")
    description: str = Field(..., description="Description of the improvement")
    message_id: UUID | None = Field(None, description="UUID of the associated message")


class AttemptGradeAnalysisEntry(BaseModel):
    """Agent-provided analysis for an attempt grade."""

    content: str = Field(..., description="Analysis content text")


class AttemptGradeHighlightEntry(BaseModel):
    """Agent-provided highlight for a strength."""

    strength_id: UUID | None = Field(None, description="UUID of the parent strength")
    section: str = Field(..., description="Highlighted text section")
    idx: int | None = Field(None, description="Index position of the highlight")


class AttemptGradeReplacementEntry(BaseModel):
    """Agent-provided replacement for an improvement."""

    improvement_id: UUID | None = Field(None, description="UUID of the parent improvement")
    section: str = Field(..., description="Original text section to replace")
    replace: str = Field(..., description="Replacement text")
    idx: int | None = Field(None, description="Index position of the replacement")


class GradeAttemptRequest(BaseModel):
    """Canonical request shape for attempt grade workflows."""

    attempt_id: UUID = Field(..., description="UUID of the attempt to grade")
    chat_id: UUID | None = Field(None, description="UUID of the chat to grade")
    resource_types: list[str] | None = Field(None, description="Resource types to include")
    user_instructions: list[str] | None = Field(None, description="Custom grading instructions")
    score: int | None = Field(None, description="Overall score for the attempt")
    passed: bool | None = Field(None, description="Whether the attempt passed")
    time_taken: int | None = Field(None, description="Time taken in seconds")
    feedbacks: list[AttemptGradeFeedbackEntry] | None = Field(None, description="Feedback entries from the agent")
    strengths: list[AttemptGradeStrengthEntry] | None = Field(None, description="Strength entries from the agent")
    improvements: list[AttemptGradeImprovementEntry] | None = Field(None, description="Improvement entries from the agent")
    analyses: list[AttemptGradeAnalysisEntry] | None = Field(None, description="Analysis entries from the agent")
    highlights: list[AttemptGradeHighlightEntry] | None = Field(None, description="Highlight entries for strengths")
    replacements: list[AttemptGradeReplacementEntry] | None = Field(None, description="Replacement entries for improvements")


# -----------------------------------------------------------------------------
# Persona types
# -----------------------------------------------------------------------------


class PersonaEntry(BaseModel):
    """Persona entry for lookup."""

    id: UUID | None = Field(None, description="UUID of the persona")
    name: str | None = Field(None, description="Name of the persona")
    icon: str | None = Field(None, description="Icon identifier for the persona")
    color: str | None = Field(None, description="Display color for the persona")
    instructions: str | None = Field(None, description="Instructions for the persona")
    examples: list[str] | None = Field(None, description="Example phrases for the persona")


# -----------------------------------------------------------------------------
# Scenario entry types (enriched from internal handlers)
# -----------------------------------------------------------------------------


class ScenarioEntry(BaseModel):
    """Scenario entry with resource metadata."""

    scenario_id: UUID | None = Field(None, description="UUID of the scenario")
    name: str | None = Field(None, description="Name of the scenario")
    description: str | None = Field(None, description="Description of the scenario")


# -----------------------------------------------------------------------------
# Rubric/Grade entry types (enriched from internal handlers)
# -----------------------------------------------------------------------------


class RubricEntry(BaseModel):
    """Rubric entry with resource metadata."""

    rubric_id: UUID | None = Field(None, description="UUID of the rubric")
    name: str | None = Field(None, description="Name of the rubric")
    description: str | None = Field(None, description="Description of the rubric")
    total_points: float | None = Field(None, description="Total available points")
    pass_points: float | None = Field(None, description="Points required to pass")


class StandardGroupEntry(BaseModel):
    """Standard group entry with resource metadata."""

    standard_group_id: UUID | None = Field(None, description="UUID of the standard group")
    name: str | None = Field(None, description="Name of the standard group")
    description: str | None = Field(None, description="Description of the standard group")
    points: float | None = Field(None, description="Total points for the group")
    pass_points: float | None = Field(None, description="Points required to pass the group")


class StandardEntry(BaseModel):
    """Standard entry with resource metadata."""

    standard_id: UUID | None = Field(None, description="UUID of the standard")
    standard_group_id: UUID | None = Field(None, description="UUID of the parent standard group")
    name: str | None = Field(None, description="Name of the standard")
    description: str | None = Field(None, description="Description of the standard")
    points: float | None = Field(None, description="Points for the standard")


# -----------------------------------------------------------------------------
# Request/Response types
# -----------------------------------------------------------------------------


class GetAttemptDetailRequest(BaseModel):
    """Client API request for attempt detail.

    Args:
        attempt_id: The attempt ID to fetch details for.
    """

    attempt_id: UUID = Field(..., description="UUID of the attempt to fetch")


class HighlightEntry(BaseModel):
    """Highlight entry within a strength."""

    section: str | None = Field(None, description="Highlighted text section")
    idx: int | None = Field(None, description="Index position of the highlight")


class ReplacementEntry(BaseModel):
    """Replacement entry within an improvement."""

    section: str | None = Field(None, description="Original text section to replace")
    replace: str | None = Field(None, description="Replacement text")
    idx: int | None = Field(None, description="Index position of the replacement")


class HintEntry(BaseModel):
    """Hint entry (practice mode only, message_id implied by parent)."""

    hint: str | None = Field(None, description="Hint text for practice mode")
    idx: int | None = Field(None, description="Index position of the hint")


class ContentEntry(BaseModel):
    """Content entry with computed display fields.

    Each content has its own display info (name/icon/color) computed from
    persona metadata on the server. Client renders each content with its
    own persona styling.
    """

    content: str | None = Field(None, description="Content text of the entry")
    name: str | None = Field(None, description="Display name (user or persona)")
    color: str | None = Field(None, description="Persona color for display")
    icon: str | None = Field(None, description="Icon identifier for display")
    created_at: str | None = Field(None, description="ISO timestamp when content was created")


class MessageFeedbackEntry(BaseModel):
    """Unified feedback entry for messages (strength or improvement).

    Combines strengths and improvements into a single type with a `type` field.
    - type="strength": has highlights (sections to highlight as good)
    - type="improvement": has replaces (sections to replace with suggestions)
    """

    id: str = Field(..., description="Unique ID: {message_id}-{type}-{index}")
    name: str | None = Field(None, description="Name of the feedback item")
    description: str | None = Field(None, description="Description of the feedback")
    type: str | None = Field(None, description="Feedback type: 'strength' or 'improvement'")
    highlights: list[HighlightEntry] | None = Field(None, description="Highlighted sections for strengths")
    replaces: list[ReplacementEntry] | None = Field(None, description="Replacement suggestions for improvements")


class FeedbackEntry(BaseModel):
    """Feedback by standard for grading state.

    standard_group_id is derived from standards metadata lookup.
    """

    id: UUID | None = Field(None, description="UUID of the feedback entry")
    standard_id: UUID | None = Field(None, description="UUID of the associated standard")
    standard_group_id: UUID | None = Field(None, description="UUID of the standard group")
    total: float | None = Field(None, description="Total score for this standard")
    feedback: str | None = Field(None, description="Feedback text for this standard")


class MessageData(BaseModel):
    """Message with contents, feedbacks, and hints.

    - contents: Array of content entries with display info (name/icon/color)
    - feedbacks: Unified strengths/improvements (only present after grading)
    - hints: Practice mode hints (only present in practice mode)
    """

    id: UUID = Field(..., description="UUID of the message")
    chat_id: UUID | None = Field(None, description="UUID of the parent chat")
    type: str | None = Field(None, description="Message type: 'query' or 'response'")
    created_at: str | None = Field(None, description="ISO timestamp when message was created")
    completed: bool | None = Field(None, description="Whether the message is complete")
    # Contents array with display info (name/icon/color per content)
    contents: list[ContentEntry] | None = Field(None, description="Content entries with display info")
    # Unified feedbacks (strengths + improvements with type field)
    feedbacks: list[MessageFeedbackEntry] | None = Field(None, description="Unified strength and improvement feedbacks")
    # Practice mode only
    hints: list[HintEntry] | None = Field(None, description="Hints for practice mode")
    # Tree branching metadata
    parent_message_id: UUID | None = Field(None, description="UUID of the parent message in tree")
    sibling_index: int | None = Field(None, description="Index among sibling messages")
    sibling_count: int | None = Field(None, description="Total number of sibling messages")


class GradeData(BaseModel):
    """Grade information for a chat (no id - not a resource)."""

    score: float | None = Field(None, description="Grade score achieved")
    passed: bool | None = Field(None, description="Whether the grade is passing")
    description: str | None = Field(None, description="Grade description text")
    time_taken: int | None = Field(None, description="Time taken in seconds")
    total_points: float | None = Field(None, description="Total available points")
    pass_points: float | None = Field(None, description="Points required to pass")


class ChatData(BaseModel):
    """Chat view data with IDs for related resources.

    Split into view categories:
    - Normal/General View: problem_statement, objectives, personas, images
    - Video/Quiz View: videos, questions, options, responses
    - Both Views: documents
    """

    id: UUID = Field(..., description="UUID of the chat")
    created_at: str | None = Field(None, description="ISO timestamp when chat was created")
    completed: bool | None = Field(None, description="Whether the chat is completed")
    is_current: bool | None = Field(None, description="Whether this is the current chat")
    position: int | None = Field(None, description="Position index of the chat")
    grade: GradeData | None = Field(None, description="Grade data for the chat")
    feedbacks: list[FeedbackEntry] | None = Field(None, description="Standard-level feedback entries")
    analyses: list[AnalysisEntry] | None = Field(None, description="Chat-level analysis content")

    # Chat-level flags
    show_problem_statement: bool | None = Field(None, description="Whether to show the problem statement")
    show_objectives: bool | None = Field(None, description="Whether to show objectives")
    copy_paste_allowed: bool | None = Field(None, description="Whether copy-paste is allowed")
    text_enabled: bool | None = Field(None, description="Whether text input is enabled")
    audio_enabled: bool | None = Field(None, description="Whether audio input is enabled")

    # Extended fields for full feature support
    grading_state: GradingStateData | None = Field(None, description="Current grading state data")
    dynamic_rubric: DynamicRubricData | None = Field(None, description="Dynamic rubric data")

    # --- Scenario resource ID ---
    scenario_id: UUID | None = Field(None, description="UUID of the associated scenario")

    # --- Normal/General View resource IDs ---
    problem_statement_id: UUID | None = Field(None, description="UUID of the problem statement")
    objective_ids: list[UUID] | None = Field(None, description="UUIDs of associated objectives")
    persona_ids: list[UUID] | None = Field(None, description="UUIDs of associated personas")
    image_ids: list[UUID] | None = Field(None, description="UUIDs of associated images")

    # --- Video/Quiz View resource IDs ---
    video_ids: list[UUID] | None = Field(None, description="UUIDs of associated videos")
    question_ids: list[UUID] | None = Field(None, description="UUIDs of associated questions")
    option_ids: list[UUID] | None = Field(None, description="UUIDs of associated options")
    responses: list[QuizResponse] | None = Field(None, description="Quiz responses for the chat")

    # --- Both Views resource IDs ---
    document_ids: list[UUID] | None = Field(None, description="UUIDs of associated documents")

    # --- Rubric/Grade resource IDs ---
    rubric_id: UUID | None = Field(None, description="UUID of the rubric")
    standard_group_ids: list[UUID] | None = Field(None, description="UUIDs of standard groups")
    standard_ids: list[UUID] | None = Field(None, description="UUIDs of standards")


class AttemptResources(BaseModel):
    """Resource maps keyed by ID string."""

    scenarios: dict[str, ScenarioEntry] | None = Field(None, description="Scenario resources keyed by ID")
    personas: dict[str, PersonaEntry] | None = Field(None, description="Persona resources keyed by ID")
    documents: dict[str, DocumentEntry] | None = Field(None, description="Document resources keyed by ID")
    images: dict[str, ImageEntry] | None = Field(None, description="Image resources keyed by ID")
    videos: dict[str, VideoEntry] | None = Field(None, description="Video resources keyed by ID")
    objectives: dict[str, ObjectiveEntry] | None = Field(None, description="Objective resources keyed by ID")
    questions: dict[str, QuestionEntry] | None = Field(None, description="Question resources keyed by ID")
    options: dict[str, OptionEntry] | None = Field(None, description="Option resources keyed by ID")
    problem_statements: dict[str, ProblemStatementEntry] | None = Field(None, description="Problem statement resources keyed by ID")
    rubrics: dict[str, RubricEntry] | None = Field(None, description="Rubric resources keyed by ID")
    standard_groups: dict[str, StandardGroupEntry] | None = Field(None, description="Standard group resources keyed by ID")
    standards: dict[str, StandardEntry] | None = Field(None, description="Standard resources keyed by ID")


class AttemptEntries(BaseModel):
    """Entry payloads grouped by entry type."""

    attempt: list[GetAttemptResponse] | None = Field(None, description="Attempt entry payloads")
    attempt_chat: list[ChatData] | None = Field(None, description="Chat entry payloads")
    attempt_message: list[MessageData] | None = Field(None, description="Message entry payloads")
    runs: GetRunListViewResponse | None = Field(None, description="Runs list view response")


class SimulationData(BaseModel):
    """Simulation metadata."""

    id: UUID | None = Field(None, description="UUID of the simulation")
    name: str | None = Field(None, description="Name of the simulation")
    description: str | None = Field(None, description="Description of the simulation")
    time_limit: int | None = Field(None, description="Time limit in seconds")
    hints_enabled: bool | None = Field(None, description="Whether hints are enabled")
    objectives_enabled: bool | None = Field(None, description="Whether objectives are enabled")
    image_input_active: bool | None = Field(None, description="Whether image input is active")
    copy_paste_allowed: bool | None = Field(None, description="Whether copy-paste is allowed")
    # Extended config fields
    practice_simulation: bool | None = Field(None, description="Whether this is a practice simulation")
    rubric_id: UUID | None = Field(None, description="UUID of the associated rubric")


class AttemptData(BaseModel):
    """Attempt-level data.

    cohort_id is only populated when practice=False.
    is_archived is only populated when practice=True.
    """

    id: UUID = Field(..., description="UUID of the attempt")
    created_at: str | None = Field(None, description="ISO timestamp when attempt was created")
    infinite_mode: bool | None = Field(None, description="Whether infinite mode is enabled")
    profile_id: UUID | None = Field(None, description="UUID of the user profile")
    profile_name: str | None = Field(None, description="Display name of the user profile")
    department_id: UUID | None = Field(None, description="UUID of the department")
    # Home mode only
    cohort_id: UUID | None = Field(None, description="UUID of the cohort (home mode only)")
    # Practice mode only
    is_archived: bool | None = Field(None, description="Whether the attempt is archived")


class TimerData(BaseModel):
    """Timer information."""

    elapsed: int | None = Field(None, description="Elapsed time in seconds")
    limit: int | None = Field(None, description="Time limit in seconds")
    exceeded: bool | None = Field(None, description="Whether the time limit was exceeded")
    formatted: str | None = Field(None, description="Formatted time string for display")
    negative: bool | None = Field(None, description="Whether the timer can go negative")


class AggregatedResults(BaseModel):
    """Aggregated results for the attempt."""

    total_score: float | None = Field(None, description="Total score across all chats")
    total_possible_points: float | None = Field(None, description="Maximum possible points")
    percentage: float | None = Field(None, description="Score as a percentage")
    passed: bool | None = Field(None, description="Whether the attempt passed overall")
    chats_completed: int | None = Field(None, description="Number of chats completed")
    total_chats: int | None = Field(None, description="Total number of chats")


class PreviousChatOption(BaseModel):
    """A single chat_entry's best previous graded attempt_chat."""

    chat_entry_id: str | None = Field(None, description="ID of the chat entry")
    scenario_name: str | None = Field(None, description="Name of the scenario")
    attempt_chat_id: str | None = Field(None, description="ID of the attempt chat")
    score: float | None = Field(None, description="Score achieved")
    percentage: float | None = Field(None, description="Score as a percentage")
    time_taken: float | None = Field(None, description="Time taken in seconds")
    position: int | None = Field(None, description="Position in the sequence")


class ContinuationOption(BaseModel):
    """A bundle of consecutive scenarios that can be reused from previous attempts."""

    scenarios: list[PreviousChatOption] = Field(..., description="Scenarios in this continuation bundle")
    total_score: float = Field(..., description="Combined score across scenarios")
    total_percentage: float | None = Field(None, description="Combined score as a percentage")
    total_time: float = Field(..., description="Combined time across scenarios")


class AvailableContinuationOptions(BaseModel):
    """Available continuation options for an attempt."""

    options: list[ContinuationOption] = Field(..., description="Available continuation option bundles")


class GetAttemptDetailResponse(BaseModel):
    """Client-facing API response for attempt detail."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    attempt_exists: bool | None = Field(None, description="Whether the attempt exists")
    access_denied: bool | None = Field(None, description="Whether access was denied")
    attempt: AttemptData | None = Field(None, description="Attempt-level data")
    simulation: SimulationData | None = Field(None, description="Simulation metadata")
    timer: TimerData | None = Field(None, description="Timer information")
    aggregated_results: AggregatedResults | None = Field(None, description="Aggregated results across chats")
    # Navigation/UI control
    current_chat_index: int | None = Field(None, description="Index of the current chat")
    expected_chat_count: int | None = Field(None, description="Expected total number of chats")
    is_active: bool | None = Field(None, description="Whether the attempt is currently active")
    is_lobby: bool | None = Field(None, description="Whether the attempt is in lobby state")
    show_results: bool | None = Field(None, description="Whether to show results view")
    should_show_controls: bool | None = Field(None, description="Whether to show UI controls")
    is_own_attempt: bool | None = Field(None, description="Whether this is the actor's own attempt")
    # Inline controls data (replaces auth/group resolution for toolbar)
    current_chat_id: str | None = Field(None, description="ID of the current chat")
    has_messages: bool = Field(False, description="Whether the chat has messages")
    # Continuation options for infinite mode
    available_continuation_options: AvailableContinuationOptions | None = Field(None, description="Continuation options for infinite mode")
    # Extended data (scenario_documents removed - use chat.documents)
    rubric_structure: RubricStructureData | None = Field(None, description="Rubric structure data")
    # Training context (for lobby flow)
    training_id: UUID | None = Field(None, description="UUID of the training")
    chat_entry_id: UUID | None = Field(None, description="UUID of the chat entry")
    # New normalized maps
    resources: AttemptResources | None = Field(None, description="Resource maps keyed by ID")
    entries: AttemptEntries | None = Field(None, description="Entry payloads by type")


# =============================================================================
# Internal data (three-layer BFF pattern)
# =============================================================================


@dataclass
class AttemptInternalData:
    """Core data container returned by get_attempt_internal().

    Contains all fetched and computed values. Consumer layers
    (get_attempt_client, get_attempt_websocket) reshape this
    into their specific response types.
    """

    # Access context
    actor_name: str | None
    attempt_exists: bool
    access_denied: bool
    is_own_attempt: bool
    practice: bool
    profiles_id: UUID | None

    # Metadata
    profile_name: str | None
    simulation_name: str | None
    training_id: UUID | None
    chat_entry_id: UUID | None

    # Config chain
    group_id: UUID | None
    agent_ids: dict[str, UUID | None] = field(default_factory=dict)

    # Raw MV results
    attempt_item: GetAttemptResponse | None = None
    chats_result: list[GetAttemptChatResponse] | None = None
    messages_result: list[GetAttemptMessageResponse] | None = None

    # Resource metadata (raw lookup dict)
    resource_meta: dict[str, dict[UUID, dict]] = field(default_factory=dict)

    # Assembled payloads
    resources_payload: AttemptResources = field(default_factory=AttemptResources)
    chats: list[ChatData] = field(default_factory=list)
    messages: list[MessageData] = field(default_factory=list)

    # Computed business logic
    attempt: AttemptData | None = None
    simulation: SimulationData | None = None
    timer: TimerData | None = None
    aggregated_results: AggregatedResults | None = None
    current_chat_index: int | None = None
    expected_chat_count: int | None = None
    is_active: bool = True
    is_lobby: bool = False
    show_results: bool = False
    should_show_controls: bool = False
    current_chat_id: str | None = None
    has_messages: bool = False
    rubric_structure: RubricStructureData | None = None
    continuation_options: AvailableContinuationOptions | None = None


# =============================================================================
# Attempt list endpoint types (unified history payload)
# =============================================================================


class AttemptListFilterOption(BaseModel):
    """Filter option for attempt history dropdowns."""

    value: str = Field(..., description="Filter option value")
    label: str | None = Field(None, description="Display label for the option")
    count: int | None = Field(None, description="Number of items matching this option")


class GetAttemptListRequest(BaseModel):
    """Request for unified attempt list/history fetch."""

    practice: bool = Field(False, description="Whether to fetch practice attempts")
    target_profile_id: UUID | None = Field(None, description="UUID of the target profile to filter by")
    start_date: str | None = Field(None, description="Start date filter (ISO format)")
    end_date: str | None = Field(None, description="End date filter (ISO format)")
    cohort_ids: list[UUID] | None = Field(default_factory=list, description="Cohort IDs to filter by")  # type: ignore[arg-type]
    department_ids: list[UUID] | None = Field(default_factory=list, description="Department IDs to filter by")  # type: ignore[arg-type]
    simulation_ids: list[UUID] | None = Field(default_factory=list, description="Simulation IDs to filter by")  # type: ignore[arg-type]
    scenario_ids: list[UUID] | None = Field(default_factory=list, description="Scenario IDs to filter by")  # type: ignore[arg-type]
    infinite_mode: bool | None = Field(None, description="Filter by infinite mode status")
    search: str | None = Field(None, description="General search string")
    profile_search: str | None = Field(None, description="Search string for profiles")
    simulation_search: str | None = Field(None, description="Search string for simulations")
    scenario_search: str | None = Field(None, description="Search string for scenarios")
    sort_by: str | None = Field("date", description="Sort field name")
    sort_order: str | None = Field("desc", description="Sort order: 'asc' or 'desc'")
    page: int = Field(0, description="Page number (0-indexed)")
    page_size: int = Field(20, description="Number of items per page")
    show_archived: bool = Field(False, description="Whether to include archived attempts")


class AttemptListItem(BaseModel):
    """Unified attempt history row shape."""

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
    score: int | None = Field(None, description="Attempt score")
    score_status: str | None = Field(None, description="Score status indicator")
    pass_pct: int | None = Field(None, description="Pass percentage threshold")
    show_view: bool | None = Field(None, description="Whether to show the view action")
    show_continue: bool | None = Field(None, description="Whether to show the continue action")
    is_archived: bool | None = Field(None, description="Whether the attempt is archived")
    practice_simulation: bool | None = Field(None, description="Whether this is a practice simulation")
    practice_scenario_id: UUID | None = Field(None, description="UUID of the practice scenario")


class GetAttemptListResponse(BaseModel):
    """Response for unified attempt list/history fetch."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    data: list[AttemptListItem] = Field(default_factory=list, description="Attempt list items")
    total_count: int = Field(0, description="Total number of matching attempts")
    page: int = Field(0, description="Current page number")
    page_size: int = Field(20, description="Number of items per page")
    total_pages: int = Field(0, description="Total number of pages")
    simulation_options: list[AttemptListFilterOption] | None = Field(None, description="Simulation filter options")
    scenario_options: list[AttemptListFilterOption] | None = Field(None, description="Scenario filter options")
    profile_options: list[AttemptListFilterOption] | None = Field(None, description="Profile filter options")


# =============================================================================
# Search endpoint types
# =============================================================================


class SearchAttemptItem(BaseModel):
    """Single attempt row in search results."""

    attempt_id: UUID = Field(..., description="UUID of the attempt")
    date: str | None = Field(None, description="ISO timestamp of the attempt")
    profile_id: UUID | None = Field(None, description="UUID of the user profile")
    profile_name: str | None = Field(None, description="Display name of the user profile")
    simulation_id: UUID | None = Field(None, description="UUID of the simulation")
    simulation_name: str | None = Field(None, description="Name of the simulation")
    department_id: UUID | None = Field(None, description="UUID of the department")
    cohort_id: UUID | None = Field(None, description="UUID of the cohort")
    practice: bool | None = Field(None, description="Whether this is a practice attempt")
    infinite_mode: bool | None = Field(None, description="Whether infinite mode is enabled")
    num_chats: int | None = Field(None, description="Number of chats in the attempt")
    is_archived: bool | None = Field(None, description="Whether the attempt is archived")
    scenario_ids: list[UUID] | None = Field(None, description="UUIDs of associated scenarios")


class SearchAttemptApiResponse(BaseModel):
    """Response for attempt search endpoint."""

    actor_name: str | None = Field(None, description="Display name of the current actor")
    attempts: list[SearchAttemptItem] | None = Field(None, description="Search result attempt items")
    simulation_filter: ListFilterSection | None = Field(None, description="Simulation filter section")
    department_filter: ListFilterSection | None = Field(None, description="Department filter section")
    total_count: int | None = Field(None, description="Total number of matching results")


# =============================================================================
# Export endpoint types
# =============================================================================


class ExportAttemptApiResponse(BaseModel):
    """Response model for attempt export."""

    content: str = Field(..., description="Exported file content")
    file_name: str = Field(..., description="Name of the exported file")
    mime_type: str = Field(..., description="MIME type of the exported file")
    row_count: int = Field(..., description="Number of rows in the export")
