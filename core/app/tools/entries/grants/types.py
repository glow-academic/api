"""Grants canonical types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateGrantResponse(BaseModel):
    id: UUID


class GetGrantResponse(BaseModel):
    id: UUID
    session_id: UUID
    expires_at: datetime
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
    profiles_id: UUID | None = None
