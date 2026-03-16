"""Response types for instructions resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetInstructionResponse(BaseModel):
    id: UUID
    template: str
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
