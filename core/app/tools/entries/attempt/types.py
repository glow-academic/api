"""Attempt entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAttemptResponse(BaseModel):
    id: UUID


class GetAttemptResponse(BaseModel):
    attempt_id: UUID
    simulation_id: UUID | None
    profile_id: UUID | None
    user_persona_id: UUID | None
    personas_id: UUID | None
    cohort_id: UUID | None
    department_id: UUID | None
    practice: bool
    attempt_created_at: datetime
    infinite_mode: bool
    num_chats: int
    is_archived: bool
    scenario_ids: list[UUID]
    chat_entry_id: UUID | None
    attempt_chat_id: UUID | None
