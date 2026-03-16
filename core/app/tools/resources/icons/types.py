"""Response types for icons resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetIconResponse(BaseModel):
    id: UUID
    name: str
    description: str
    value: str
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
