"""Attempt home entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateAttemptHomeResponse(BaseModel):
    attempt_id: UUID
    home_id: UUID


class GetAttemptHomeResponse(BaseModel):
    attempt_id: UUID
    home_id: UUID
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
    session_id: UUID
