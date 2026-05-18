"""Types for simulations resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetSimulationResponse(BaseModel):
    id: UUID
    name: str
    description: str
    department_ids: list[UUID]
    scenario_ids: list[UUID]
    scenario_rubric_ids: list[UUID]
    scenario_time_limit_ids: list[UUID]
    scenario_position_ids: list[UUID]
    scenario_flag_ids: list[UUID]
    practice: bool
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
