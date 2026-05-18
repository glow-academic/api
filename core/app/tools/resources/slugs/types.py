"""Response types for slugs resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetSlugResponse(BaseModel):
    id: UUID
    value: str
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
