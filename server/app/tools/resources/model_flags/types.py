"""Types for model_flags resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetModelFlagResponse(BaseModel):
    id: UUID
    model_id: UUID
    flag_id: UUID
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
