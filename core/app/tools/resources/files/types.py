"""Types for files resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetFileResponse(BaseModel):
    id: UUID
    active: bool
    generated: bool
    mcp: bool
    created_at: datetime
