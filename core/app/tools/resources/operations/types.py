"""Types for operations resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetOperationResponse(BaseModel):
    id: UUID
    operation: str
    active: bool
    generated: bool
    mcp: bool
    created_at: datetime
