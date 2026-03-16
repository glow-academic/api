"""Response types for texts resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetTextResponse(BaseModel):
    id: UUID
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
