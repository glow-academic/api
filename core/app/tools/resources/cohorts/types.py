"""Types for cohorts resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetCohortResponse(BaseModel):
    id: UUID
    name: str
    description: str
    department_ids: list[UUID]
    simulation_ids: list[UUID]
    profile_ids: list[UUID]
    profile_persona_ids: list[UUID]
    simulation_position_ids: list[UUID]
    simulation_availability_ids: list[UUID]
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
