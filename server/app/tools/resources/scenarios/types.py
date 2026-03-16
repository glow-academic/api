"""Types for scenarios resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetScenarioResponse(BaseModel):
    id: UUID
    name: str
    description: str
    problem_statement_enabled: bool
    objectives_enabled: bool
    video_enabled: bool
    images_enabled: bool
    questions_enabled: bool
    department_ids: list[UUID]
    persona_ids: list[UUID]
    parameter_field_ids: list[UUID]
    document_ids: list[UUID]
    objective_ids: list[UUID]
    image_ids: list[UUID]
    video_ids: list[UUID]
    question_ids: list[UUID]
    option_ids: list[UUID]
    problem_statement_ids: list[UUID]
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
