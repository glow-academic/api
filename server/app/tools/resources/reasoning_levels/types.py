"""Types for reasoning_levels resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetReasoningLevelResponse(BaseModel):
    id: UUID
    reasoning_level: str
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
