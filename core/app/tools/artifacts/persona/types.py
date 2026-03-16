"""Persona artifact types — tool layer."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class GetPersonasResponse(BaseModel):
    id: UUID
    created_at: datetime
    updated_at: datetime
    generated: bool
    mcp: bool
    active: bool
    # Junction IDs — None when not requested
    name_ids: list[UUID] | None = None
    description_ids: list[UUID] | None = None
    color_ids: list[UUID] | None = None
    department_ids: list[UUID] | None = None
    example_ids: list[UUID] | None = None
    flag_ids: list[UUID] | None = None
    icon_ids: list[UUID] | None = None
    instruction_ids: list[UUID] | None = None
    parameter_field_ids: list[UUID] | None = None
    persona_ids: list[UUID] | None = None
    voice_ids: list[UUID] | None = None


class CreatePersonaResponse(BaseModel):
    id: UUID


class UpdatePersonaResponse(BaseModel):
    id: UUID


class DeletePersonasResponse(BaseModel):
    deleted_ids: list[UUID]
