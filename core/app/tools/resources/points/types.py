"""Types for points resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetPointResponse(BaseModel):
    id: UUID
    value: int
    type: str = "total"  # "total" or "pass"
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
