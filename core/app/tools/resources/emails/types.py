"""Response types for emails resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetEmailResponse(BaseModel):
    id: UUID
    email: str
    is_primary: bool
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
