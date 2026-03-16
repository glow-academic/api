"""Types for objectives resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetObjectiveResponse(BaseModel):
    id: UUID
    objective: str
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
