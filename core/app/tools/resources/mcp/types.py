"""Types for mcp resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateMcpResponse(BaseModel):
    id: UUID


class GetMcpResponse(BaseModel):
    id: UUID
    agent_id: UUID
    name: str
    description: str
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
