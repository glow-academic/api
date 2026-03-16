"""Types for scenario_positions resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetScenarioPositionResponse(BaseModel):
    id: UUID
    scenario_id: UUID
    value: int
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
