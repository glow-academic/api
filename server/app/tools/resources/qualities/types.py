"""Types for qualities resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetQualityResponse(BaseModel):
    id: UUID
    quality: str
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
