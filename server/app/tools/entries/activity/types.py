"""Activity entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateActivityResponse(BaseModel):
    id: UUID


class GetActivityResponse(BaseModel):
    id: UUID
    profile_id: UUID | None
    session_id: UUID | None
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
