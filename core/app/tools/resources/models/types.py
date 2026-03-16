"""Response types for models resource."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetModelResponse(BaseModel):
    id: UUID
    name: str | None
    description: str | None
    value: str
    provider_id: UUID | None
    department_ids: list[UUID]
    temperature_level_ids: list[UUID]
    reasoning_level_ids: list[UUID]
    quality_ids: list[UUID]
    voice_ids: list[UUID]
    modality_ids: list[UUID]
    created_at: datetime
    active: bool
    mcp: bool
    generated: bool
