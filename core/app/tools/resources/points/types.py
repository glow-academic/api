"""Types for points resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetPointResponse(BaseModel):
    id: UUID
    value: int
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
