"""Persona entry types — handcrafted, co-located with handler."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CreatePersonaResponse(BaseModel):
    id: UUID


class GetPersonaResponse(BaseModel):
    id: UUID
    created_at: datetime
    active: bool
    generated: bool
    mcp: bool
    session_id: UUID | None
