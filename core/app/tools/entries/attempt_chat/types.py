"""Attempt chat entry types — handcrafted, co-located with handler."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateAttemptChatResponse(BaseModel):
    id: UUID


class GetAttemptChatResponse(BaseModel):
    chat_id: UUID
    attempt_id: UUID
    chat_entry_id: UUID | None
    group_id: UUID | None
    profile_id: UUID | None
    cohort_id: UUID | None
    department_id: UUID | None
    simulation_id: UUID | None
    scenario_id: UUID | None
    persona_ids: list[UUID] | None
    rubric_id: UUID | None
    grade_score: int | None
    grade_total_points: int | None
    grade_pass_points: int | None
    grade_passed: bool | None
    grade_time_taken: int | None
    completed: bool | None
    attempt_number: int | None
    chat_created_at: datetime | None
    attempt_date: date | None
    attempt_type: str | None
    is_archived: bool | None
    infinite_mode: bool | None
    document_ids: list[UUID] | None
    # Training config flags
    copy_paste_allowed: bool | None = None
    text_enabled: bool | None = None
    audio_enabled: bool | None = None
    hints_enabled: bool | None = None
    show_images: bool | None = None
    show_objectives: bool | None = None
    show_problem_statement: bool | None = None
    time_limit_seconds: int | None = None
    negative: bool | None = None
    # Resource ID arrays
    problem_statement_id: UUID | None = None
    objective_ids: list[UUID] | None = None
    question_ids: list[UUID] | None = None
    option_ids: list[UUID] | None = None
    image_ids: list[UUID] | None = None
    video_ids: list[UUID] | None = None
    standard_group_ids: list[UUID] | None = None
    standard_ids: list[UUID] | None = None


class ChatItem(BaseModel):
    """Single chat row from attempt_chat_mv."""

    # Primary key
    chat_id: UUID

    # Foreign keys
    attempt_id: UUID
    chat_entry_id: UUID | None = None
    group_id: UUID | None = None
    attempt_chat_id: UUID | None = None

    # Resource IDs
    profile_id: UUID
    cohort_id: UUID | None = None
    department_id: UUID | None = None
    simulation_id: UUID | None = None
    scenario_id: UUID | None = None
    persona_ids: list[UUID] | None = None
    rubric_id: UUID | None = None

    # Grade measures (raw values — consumers compute grade_percent)
    grade_score: int | None = None
    grade_total_points: int | None = None
    grade_pass_points: int | None = None
    grade_passed: bool | None = None
    grade_time_taken: int | None = None

    # Chat state
    completed: bool = False
    attempt_number: int = 0

    # Timestamps
    chat_created_at: datetime | None = None
    attempt_date: date | None = None

    # Filters
    attempt_type: str | None = None  # 'general' | 'practice'
    is_archived: bool = False
    infinite_mode: bool = False

    # Enrichment fields (set by consumers after fetching, not from MV)
    num_messages_total: int = 0
    avg_response_sec: float | None = None
    document_ids: list[UUID] = Field(default_factory=list)

    @property
    def grade_percent(self) -> float | None:
        """Compute grade percentage from raw score and total points."""
        if (
            self.grade_score is not None
            and self.grade_total_points is not None
            and self.grade_total_points > 0
        ):
            return round((self.grade_score / self.grade_total_points) * 100, 2)
        return None

    @property
    def passed(self) -> bool | None:
        """Alias for grade_passed (compat with old *FactsItem types)."""
        return self.grade_passed

    @property
    def persona_id(self) -> UUID | None:
        """First persona_id for compat with old *FactsItem types."""
        return self.persona_ids[0] if self.persona_ids else None

    @property
    def time_taken_seconds(self) -> int | None:
        """Alias for grade_time_taken (compat with old *FactsItem types)."""
        return self.grade_time_taken
