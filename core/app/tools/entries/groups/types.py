"""Groups entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateGroupResponse(BaseModel):
    id: UUID


class GetGroupResponse(BaseModel):
    id: UUID
    session_id: UUID
    created_at: datetime
    name: str
    active: bool
    mcp: bool
    generated: bool
