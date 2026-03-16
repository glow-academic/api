"""Types for temperature_levels resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetTemperatureLevelResponse(BaseModel):
    id: UUID
    temperature: float
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
