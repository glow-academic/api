"""Client-facing Attempt WebSocket types.

Canonical location for all Attempt* payload and event models used by the
v5 WebSocket (and HTTP) transport layer.  Previously defined inline in
``app.socket.v5.client.types``; moved here so that domain code can import
them without reaching into the socket layer.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MESSAGE_ENTRY_TYPES = ["contents", "hints"]

# ---------------------------------------------------------------------------
# Attempt room management
# ---------------------------------------------------------------------------


class AttemptJoinPayload(BaseModel):
    """Client-to-server: join a chat room for real-time updates."""

    chat_id: UUID = Field(..., description="UUID of the chat to join")


class AttemptLeavePayload(BaseModel):
    """Client-to-server: leave a chat room."""

    chat_id: UUID = Field(..., description="UUID of the chat to leave")


class AttemptJoinedEvent(BaseModel):
    """Server-to-client: successfully joined a chat room."""

    chat_id: str = Field(..., description="UUID of the chat joined")
    success: bool = Field(..., description="Whether the join succeeded")


# ---------------------------------------------------------------------------
# Attempt state management
# ---------------------------------------------------------------------------


class AttemptStartPayload(BaseModel):
    """Client-to-server: create a new attempt."""

    home_id: UUID | None = Field(None, description="UUID of the home resource")
    practice_id: UUID | None = Field(None, description="UUID of the practice resource")
    infinite_mode: bool = Field(False, description="Whether to run in infinite mode")

    @model_validator(mode="after")
    def _exactly_one_parent(self) -> "AttemptStartPayload":
        if not self.home_id and not self.practice_id:
            raise ValueError("Either home_id or practice_id must be provided")
        if self.home_id and self.practice_id:
            raise ValueError("Only one of home_id or practice_id can be provided")
        return self


class AttemptNextPayload(BaseModel):
    """Client-to-server: proceed to the next scenario in an existing attempt."""

    attempt_id: UUID = Field(..., description="UUID of the attempt")
    draft_id: UUID | None = Field(None, description="UUID of the draft to use")


class AttemptStartedEvent(BaseModel):
    """Server-to-client: new attempt created."""

    attempt_id: str = Field(..., description="UUID of the attempt")
    chat_entry_id: str = Field(..., description="UUID of the initial chat entry")


class AttemptEndPayload(BaseModel):
    """Client-to-server: end a single chat within an attempt."""

    attempt_id: UUID = Field(..., description="UUID of the attempt")
    chat_id: UUID = Field(..., description="UUID of the chat to end")
    grade: bool = Field(True, description="Whether to grade this chat")


class AttemptChatStartedEvent(BaseModel):
    """Server-to-client: new chat created within an attempt."""

    attempt_id: str = Field(..., description="UUID of the attempt")
    chat_id: str = Field(..., description="UUID of the new chat")


class AttemptChatEndedEvent(BaseModel):
    """Server-to-client: single chat ended."""

    chat_id: str = Field(..., description="UUID of the ended chat")
    is_attempt_finished: bool | None = Field(None, description="Whether the entire attempt is finished")
    grade_id: str | None = Field(None, description="UUID of the grade record")


class AttemptEndAllPayload(BaseModel):
    """Client-to-server: end all remaining chats in an attempt."""

    attempt_id: UUID = Field(..., description="UUID of the attempt")


class AttemptEndedEvent(BaseModel):
    """Server-to-client: entire attempt ended (all scenarios complete)."""

    attempt_id: str = Field(..., description="UUID of the attempt")
    success: bool = Field(..., description="Whether the attempt ended successfully")
    all_scenarios_complete: bool = Field(False, description="Whether all scenarios are complete")
    message: str | None = Field(None, description="Event message content")


class AttemptUsePreviousPayload(BaseModel):
    """Client-to-server: reuse attempt_chats from a previous attempt.

    previous_chat_map: {chat_entry_id: attempt_chat_id}
    """

    attempt_id: UUID = Field(..., description="UUID of the attempt")
    previous_chat_map: dict[str, str] = Field(..., description="Map of chat_entry_id to attempt_chat_id")


class AttemptErrorEvent(BaseModel):
    """Server-to-client: attempt error."""

    chat_id: str | None = Field(None, description="UUID of the related chat")
    type: str | None = Field(None, description="Classification of the error")
    message: str = Field(..., description="Error message")


# ---------------------------------------------------------------------------
# Attempt message events
# ---------------------------------------------------------------------------


class AttemptMessagePayload(BaseModel):
    """Client-to-server: send a text message in an attempt chat (modality=call)."""

    attempt_id: UUID = Field(..., description="UUID of the attempt")
    chat_id: UUID = Field(..., description="UUID of the chat")
    message: str = Field(..., description="Text message content")
    parent_message_id: UUID | None = Field(None, description="UUID of the parent message for threading")


class AttemptUserCompleteEvent(BaseModel):
    """Server-to-client: user message finalized."""

    chat_id: str = Field(..., description="UUID of the chat")
    message_id: str = Field(..., description="UUID of the message")
    content: str = Field(..., description="Final message content")
    created_at: str = Field(..., description="ISO 8601 timestamp of message creation")
    item_id: str | None = Field(None, description="Audio VAD item identifier")


class AttemptAssistantStartEvent(BaseModel):
    """Server-to-client: assistant message generation starting."""

    chat_id: str = Field(..., description="UUID of the chat")
    message_id: str = Field(..., description="UUID of the assistant message")
    created_at: str = Field(..., description="ISO 8601 timestamp of generation start")


class AttemptAssistantProgressEvent(BaseModel):
    """Server-to-client: assistant generation progress."""

    chat_id: str = Field(..., description="UUID of the chat")
    content_type: str = Field(..., description="Content type: 'delta' or 'audio'")
    content: str | None = Field(None, description="Text content delta")
    audio: Any | None = Field(None, description="Audio content payload")


class AttemptAssistantCompleteEvent(BaseModel):
    """Server-to-client: assistant message generation complete."""

    chat_id: str = Field(..., description="UUID of the chat")
    message_id: str = Field(..., description="UUID of the assistant message")
    content: str | None = Field(None, description="Final assistant message content")


class AttemptAssistantHintsEvent(BaseModel):
    """Server-to-client: hints created during assistant generation."""

    chat_id: str = Field(..., description="UUID of the chat")
    hints: list[dict[str, Any]] = Field(..., description="List of hint objects")


# ---------------------------------------------------------------------------
# Attempt grade events
# ---------------------------------------------------------------------------


class AttemptGradePayload(BaseModel):
    """Client-to-server: trigger grading for an attempt chat."""

    attempt_id: UUID = Field(..., description="UUID of the attempt")
    chat_id: UUID | None = Field(None, description="UUID of the chat to grade")
    resource_types: list[str] | None = Field(None, description="Resource types to grade")
    user_instructions: list[str] | None = Field(None, description="Custom grading instructions")


class AttemptGradeStartEvent(BaseModel):
    """Server-to-client: grading began."""

    chat_id: str = Field(..., description="UUID of the chat being graded")
    grade_id: str | None = Field(None, description="UUID of the grade record")


class AttemptGradeProgressEvent(BaseModel):
    """Server-to-client: per-criterion grade result."""

    chat_id: str = Field(..., description="UUID of the chat being graded")
    grade_id: str | None = Field(None, description="UUID of the grade record")
    resource_type: str | None = Field(None, description="Type of resource being graded")
    entry: dict[str, Any] | None = Field(None, description="Grade criterion entry data")


class AttemptGradeCompleteEvent(BaseModel):
    """Server-to-client: aggregate grade result."""

    chat_id: str = Field(..., description="UUID of the graded chat")
    grade_id: str | None = Field(None, description="UUID of the grade record")


# ---------------------------------------------------------------------------
# Attempt stop events
# ---------------------------------------------------------------------------


class AttemptStopPayload(BaseModel):
    """Client-to-server: stop message generation."""

    chat_id: UUID = Field(..., description="UUID of the chat to stop generating")


class AttemptStoppedEvent(BaseModel):
    """Server-to-client: message generation stopped."""

    chat_id: str = Field(..., description="UUID of the chat")
    success: bool = Field(..., description="Whether the stop succeeded")
    message: str | None = Field(None, description="Event message content")


# ---------------------------------------------------------------------------
# Attempt response events
# ---------------------------------------------------------------------------


class AttemptResponsePayload(BaseModel):
    """Client-to-server: submit a video question response."""

    chat_id: UUID = Field(..., description="UUID of the chat")
    question_id: UUID = Field(..., description="UUID of the question being answered")
    option_ids: list[UUID] = Field(..., description="List of selected option UUIDs")


class AttemptResponseResultEvent(BaseModel):
    """Server-to-client: response submission result."""

    success: bool = Field(..., description="Whether the response was submitted")
    message: str | None = Field(None, description="Event message content")
    is_correct: bool | None = Field(None, description="Whether the response was correct")
    response_id: str | None = Field(None, description="UUID of the saved response")


# ---------------------------------------------------------------------------
# Audio events
# ---------------------------------------------------------------------------


class AttemptAudioStartPayload(BaseModel):
    """Client-to-server: start a voice session."""

    chat_id: UUID = Field(..., description="UUID of the chat for voice session")


class AttemptAudioStopPayload(BaseModel):
    """Client-to-server: stop a voice session."""

    chat_id: UUID = Field(..., description="UUID of the chat for voice session")


class AttemptUserStartEvent(BaseModel):
    """Server-to-client: user message started (text or audio)."""

    chat_id: str = Field(..., description="UUID of the chat")
    message_id: str = Field(..., description="UUID of the user message")
    created_at: str = Field(..., description="ISO 8601 timestamp of message creation")
    item_id: str | None = Field(None, description="Audio VAD item identifier")


class AttemptUserProgressEvent(BaseModel):
    """Server-to-client: user transcription progress (audio only)."""

    chat_id: str = Field(..., description="UUID of the chat")
    item_id: str | None = Field(None, description="Audio VAD item identifier")
    transcript: str = Field(..., description="Current transcription text")


class AttemptUserDeltaEvent(BaseModel):
    """Server-to-client: voice transcription delta (deprecated alias)."""

    chat_id: str = Field(..., description="UUID of the chat")
    item_id: str = Field(..., description="Audio VAD item identifier")
    transcript: str = Field(..., description="Incremental transcription delta")


class AttemptAudioReadyEvent(BaseModel):
    """Server-to-client: voice session is ready."""

    chat_id: str = Field(..., description="UUID of the chat")
    success: bool = Field(..., description="Whether the voice session is ready")
    message: str | None = Field(None, description="Event message content")


class AttemptAudioEndedEvent(BaseModel):
    """Server-to-client: voice session ended."""

    chat_id: str = Field(..., description="UUID of the chat")
    success: bool = Field(..., description="Whether the voice session ended cleanly")
    message: str | None = Field(None, description="Event message content")
