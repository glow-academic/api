"""Types for arg_positions resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetArgPositionResponse(BaseModel):
    id: UUID
    args_id: UUID
    value: int
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
