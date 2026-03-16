"""Types for model_positions resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetModelPositionResponse(BaseModel):
    id: UUID
    model_id: UUID
    value: int
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
