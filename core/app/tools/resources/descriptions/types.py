"""Response types for descriptions resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetDescriptionResponse(BaseModel):
    id: UUID
    description: str
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
