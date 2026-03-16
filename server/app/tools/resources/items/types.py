"""Types for items resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetItemResponse(BaseModel):
    id: UUID
    name: str
    description: str
    encrypted: bool
    position: int
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
