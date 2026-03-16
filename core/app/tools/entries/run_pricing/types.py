"""Run pricing entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateRunPricingEntryResponse(BaseModel):
    id: UUID


class CreateRunPricingResponse(BaseModel):
    id: UUID


class GetRunPricingResponse(BaseModel):
    id: UUID
    pricing_type: str
    count: int
    run_id: UUID
    session_id: UUID | None
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
