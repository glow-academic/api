"""Response types for flags resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetFlagResponse(BaseModel):
    id: UUID
    name: str
    description: str
    type: str
    icon: str
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
    value: bool
