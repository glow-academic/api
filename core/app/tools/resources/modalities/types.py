"""Types for modalities resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetModalityResponse(BaseModel):
    id: UUID
    modality: str
    is_input: bool
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
