"""Problems entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateProblemResponse(BaseModel):
    id: UUID


class GetProblemResponse(BaseModel):
    id: UUID
    profile_id: UUID | None
    session_id: UUID
    type: str
    message: str
    resolved: bool
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
