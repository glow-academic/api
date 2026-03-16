"""Attempt message entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAttemptMessageResponse(BaseModel):
    id: UUID


class GetAttemptMessageResponse(BaseModel):
    message_id: UUID
    chat_id: UUID | None
    attempt_id: UUID | None
    type: str | None
    created_at: datetime | None
    completed: bool | None
    text_id: UUID | None
    history_file_path: str | None
    audio_id: UUID | None
    parent_message_id: UUID | None = None
    sibling_index: int | None = None
    sibling_count: int | None = None
