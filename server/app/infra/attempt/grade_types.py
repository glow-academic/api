"""Canonical attempt grading request types shared across transports."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class AttemptGradeFeedbackEntry(BaseModel):
    feedback: str = Field(..., description="Feedback text content")
    total: int | None = Field(None, description="Total score for this feedback entry")


class AttemptGradeStrengthEntry(BaseModel):
    name: str = Field(..., description="Name of the identified strength")
    description: str = Field(..., description="Description of the strength")
    message_id: UUID | None = Field(None, description="UUID of the related message")


class AttemptGradeImprovementEntry(BaseModel):
    name: str = Field(..., description="Name of the identified improvement area")
    description: str = Field(..., description="Description of the improvement")
    message_id: UUID | None = Field(None, description="UUID of the related message")


class AttemptGradeAnalysisEntry(BaseModel):
    content: str = Field(..., description="Analysis text content")


class AttemptGradeHighlightEntry(BaseModel):
    strength_id: UUID | None = Field(None, description="UUID of the parent strength")
    section: str = Field(..., description="Text section to highlight")
    idx: int | None = Field(None, description="Index position of the highlight")


class AttemptGradeReplacementEntry(BaseModel):
    improvement_id: UUID | None = Field(None, description="UUID of the parent improvement")
    section: str = Field(..., description="Original text section to replace")
    replace: str = Field(..., description="Replacement text")
    idx: int | None = Field(None, description="Index position of the replacement")


class GradeAttemptRequest(BaseModel):
    attempt_id: UUID = Field(..., description="UUID of the attempt to grade")
    chat_id: UUID | None = Field(None, description="UUID of the chat to grade")
    resource_types: list[str] | None = Field(None, description="Resource types to include in grading")
    user_instructions: list[str] | None = Field(None, description="Custom grading instructions")
    score: int | None = Field(None, description="Overall score for the attempt")
    passed: bool | None = Field(None, description="Whether the attempt passed")
    time_taken: int | None = Field(None, description="Time taken in seconds")
    feedbacks: list[AttemptGradeFeedbackEntry] | None = Field(None, description="Feedback entries from the grader")
    strengths: list[AttemptGradeStrengthEntry] | None = Field(None, description="Strength entries from the grader")
    improvements: list[AttemptGradeImprovementEntry] | None = Field(None, description="Improvement entries from the grader")
    analyses: list[AttemptGradeAnalysisEntry] | None = Field(None, description="Analysis entries from the grader")
    highlights: list[AttemptGradeHighlightEntry] | None = Field(None, description="Highlight entries for strengths")
    replacements: list[AttemptGradeReplacementEntry] | None = Field(None, description="Replacement entries for improvements")
