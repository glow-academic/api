"""Grant consumptions entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateGrantConsumptionResponse(BaseModel):
    id: UUID


class GetGrantConsumptionResponse(BaseModel):
    id: UUID
    grant_id: UUID
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
