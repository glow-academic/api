"""Response types for values resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetValueResponse(BaseModel):
    id: UUID
    value: str
    type: str
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
