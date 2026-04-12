"""Group names entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateGroupNameResponse(BaseModel):
    id: UUID


class GetGroupNameResponse(BaseModel):
    id: UUID
    group_id: UUID
    name: str
    created_at: datetime
    generated: bool
    mcp: bool
