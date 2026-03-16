"""Types for scenario_time_limits resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetScenarioTimeLimitResponse(BaseModel):
    id: UUID
    scenario_id: UUID
    time_limit_seconds: int
    negative: bool
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
