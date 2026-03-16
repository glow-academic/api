"""Types for personas resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetPersonaResponse(BaseModel):
    id: UUID
    name: str
    description: str
    icon: str
    color: str
    department_ids: list[UUID]
    instructions: str
    examples: list[str]
    parameter_field_ids: list[UUID]
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
