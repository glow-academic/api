"""Logouts entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateLogoutResponse(BaseModel):
    id: UUID


class GetLogoutResponse(BaseModel):
    id: UUID
    profile_id: UUID | None
    session_id: UUID | None
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
