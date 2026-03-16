"""Types for examples resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetExampleResponse(BaseModel):
    id: UUID
    example: str
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
