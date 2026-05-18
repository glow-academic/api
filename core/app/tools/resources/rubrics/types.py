"""Types for rubrics resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetRubricResponse(BaseModel):
    id: UUID
    name: str
    description: str
    department_ids: list[UUID]
    total_points: int
    pass_points: int
    simulation_rubric: bool
    video_rubric: bool
    standard_group_ids: list[UUID]
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
