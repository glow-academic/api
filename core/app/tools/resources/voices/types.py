"""Response types for voices resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetVoiceResponse(BaseModel):
    id: UUID
    voice: str
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
