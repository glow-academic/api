"""Types for evals resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetEvalResponse(BaseModel):
    id: UUID
    name: str
    description: str
    department_ids: list[UUID]
    model_ids: list[UUID]
    model_rubric_ids: list[UUID]
    model_flag_ids: list[UUID]
    model_position_ids: list[UUID]
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
