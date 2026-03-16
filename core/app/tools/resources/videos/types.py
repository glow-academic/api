"""Types for videos resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetVideoResponse(BaseModel):
    id: UUID
    name: str
    description: str
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
