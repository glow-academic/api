"""Types for request_limits resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetRequestLimitResponse(BaseModel):
    id: UUID
    requests_per_day: int
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
