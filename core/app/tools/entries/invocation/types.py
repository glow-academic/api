"""Invocation entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreateInvocationResponse(BaseModel):
    id: UUID


class GetInvocationResponse(BaseModel):
    id: UUID
    benchmark_id: UUID
    session_id: UUID | None
    use_custom: bool
    position: int
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
    department_ids: list[UUID]
    description_ids: list[UUID]
    flag_ids: list[UUID]
    key_ids: list[UUID]
    modality_ids: list[UUID]
    model_flag_ids: list[UUID]
    model_position_ids: list[UUID]
    model_rubric_ids: list[UUID]
    model_ids: list[UUID]
    name_ids: list[UUID]
    quality_ids: list[UUID]
    reasoning_level_ids: list[UUID]
    temperature_level_ids: list[UUID]
    voice_ids: list[UUID]
