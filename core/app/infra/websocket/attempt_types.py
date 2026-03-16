"""Pydantic models for attempt_* internal events.

Canonical location for attempt internal event data types.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


# --- Lifecycle ---
class AttemptStartRequestData(BaseModel):
    sid: str
    attempt_id: str


class AttemptChatRequestData(BaseModel):
    sid: str
    attempt_id: str
    attempt_chat_id: str
    profile_id: str


class GenerateRequestData(BaseModel):
    sid: str
    profile_id: str
    artifact_types: list[dict[str, str]]
    artifact_id: str
    resource_types: list[str]
    save: bool = True
    draft_id: str | None = None
    user_instructions: list[str] | None = None
    run_id: str | None = None
    group_id: str | None = None
    modality: str = "call"
    extra_messages: list[dict[str, str]] | None = None
    metadata: dict[str, Any] | None = None


class AttemptProceedData(BaseModel):
    sid: str
    attempt_id: str
    group_id: str
    profile_id: str | None = None
    session_id: str | None = None
    draft_id: str | None = None
    force_proceed: bool = False
    completed_chat_id: str | None = None
    complete_all: bool = False


class AttemptStartedData(BaseModel):
    sid: str
    attempt_id: str
    chat_entry_id: str


class AttemptEndedData(BaseModel):
    sid: str
    attempt_id: str
    success: bool
    all_scenarios_complete: bool = False
    message: str | None = None


class AttemptErrorData(BaseModel):
    sid: str
    error_type: str
    message: str
    chat_id: str | None = None


# --- Chat ---
class AttemptChatStartedData(BaseModel):
    sid: str
    attempt_id: str
    chat_id: str


class AttemptChatEndedData(BaseModel):
    sid: str
    chat_id: str
    is_attempt_finished: bool | None = None
    grade_id: str | None = None


class AttemptJoinedData(BaseModel):
    sid: str
    chat_id: str
    success: bool = True


# --- User (received — pre-DB, emitted by client/audio handlers) ---
class AttemptUserReceivedStartData(BaseModel):
    sid: str
    chat_id: str
    run_id: str
    profile_id: str
    session_id: str | None = None
    item_id: str | None = None
    rooms: list[str] | None = None


class AttemptUserReceivedProgressData(BaseModel):
    sid: str
    chat_id: str
    item_id: str | None = None
    transcript: str = ""
    rooms: list[str] | None = None


class AttemptUserReceivedCompleteData(BaseModel):
    sid: str
    chat_id: str
    run_id: str
    content: str
    session_id: str | None = None
    item_id: str | None = None
    rooms: list[str] | None = None
    audio_upload_id: str | None = None


# --- User (confirmed — post-DB, emitted to server/ layer) ---
class AttemptUserStartData(BaseModel):
    sid: str
    chat_id: str
    message_id: str
    created_at: str
    item_id: str | None = None
    rooms: list[str] | None = None


class AttemptUserProgressData(BaseModel):
    sid: str
    chat_id: str
    item_id: str | None = None
    transcript: str = ""
    rooms: list[str] | None = None


class AttemptUserCompleteData(BaseModel):
    sid: str
    chat_id: str
    message_id: str
    content: str
    created_at: str
    rooms: list[str] | None = None
    item_id: str | None = None


# --- Assistant ---
class AttemptAssistantStartData(BaseModel):
    sid: str
    chat_id: str
    message_id: str
    created_at: str


class AttemptAssistantProgressData(BaseModel):
    sid: str
    chat_id: str
    content_type: str
    content: str | None = None
    audio: Any | None = None


class AttemptAssistantCompleteData(BaseModel):
    sid: str
    chat_id: str
    message_id: str
    content: str | None = None


class AttemptAssistantHintsData(BaseModel):
    sid: str
    chat_id: str
    hints: list[dict[str, Any]]


# --- Grade ---
class AttemptGradeStartData(BaseModel):
    sid: str
    chat_id: str
    grade_id: str | None = None


class AttemptGradeProgressData(BaseModel):
    sid: str
    chat_id: str
    grade_id: str | None = None
    resource_type: str | None = None
    entry: dict[str, Any] | None = None


class AttemptGradeCompleteData(BaseModel):
    sid: str
    chat_id: str
    grade_id: str | None = None


# --- Control ---
class AttemptStoppedData(BaseModel):
    sid: str
    chat_id: str
    success: bool
    message: str | None = None
    rooms: list[str] | None = None


# --- Audio ---
class AttemptAudioReadyData(BaseModel):
    sid: str
    chat_id: str
    success: bool = True
    message: str | None = None


class AttemptAudioEndedData(BaseModel):
    sid: str
    chat_id: str
    success: bool = True
    message: str | None = None


# --- Response ---
class AttemptResponseResultData(BaseModel):
    sid: str
    success: bool
    message: str | None = None
    is_correct: bool | None = None
    response_id: str | None = None
