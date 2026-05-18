"""Response types for agents resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetAgentResponse(BaseModel):
    id: UUID
    name: str | None
    description: str | None
    department_ids: list[UUID]
    temperature: float | None
    reasoning: str | None
    quality: str | None
    model_id: UUID | None
    prompt_id: UUID | None
    rubric_id: UUID | None
    tool_ids: list[UUID]
    instruction_ids: list[UUID]
    voices: list[str]
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
