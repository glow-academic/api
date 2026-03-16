"""Attempt practice entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAttemptPracticeResponse(BaseModel):
    attempt_id: UUID
    practice_id: UUID


class GetAttemptPracticeResponse(BaseModel):
    attempt_id: UUID
    practice_id: UUID
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
    session_id: UUID
