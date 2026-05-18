"""Response types for endpoints resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetEndpointResponse(BaseModel):
    id: UUID
    base_url: str
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
