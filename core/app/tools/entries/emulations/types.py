"""Emulations entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateEmulationResponse(BaseModel):
    id: UUID


class GetEmulationResponse(BaseModel):
    id: UUID
    profile_id: UUID | None
    grant_id: UUID
    session_id: UUID
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
