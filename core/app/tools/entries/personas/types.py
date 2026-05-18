"""Personas entry types."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreatePersonasResponse(BaseModel):
    id: UUID


class GetPersonasResponse(BaseModel):
    id: UUID
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
    session_id: UUID | None
    persona_ids: list[UUID]
