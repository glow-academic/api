"""Types for pricing resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetPricingResponse(BaseModel):
    id: UUID
    pricing_type: str
    price: float
    unit_name: str
    unit_category: str
    unit_value: int
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
