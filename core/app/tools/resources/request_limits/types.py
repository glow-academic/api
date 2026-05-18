"""Types for request_limits resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetRequestLimitResponse(BaseModel):
    id: UUID
    limit: int
    interval: str
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
