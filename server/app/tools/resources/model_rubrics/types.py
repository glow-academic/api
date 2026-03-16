"""Types for model_rubrics resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetModelRubricResponse(BaseModel):
    id: UUID
    model_id: UUID
    rubric_id: UUID
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
